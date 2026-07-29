import base64

from odoo import _, http
from odoo.http import request
from odoo.tools.mimetypes import guess_mimetype

# A phone photo is a couple of megabytes. Anything far above that is not a
# picture of a ring, and the link is public by design: whoever is standing in
# front of the counter screen can read the QR.
MAX_PHOTO_BYTES = 12 * 1024 * 1024

# What a camera produces, and nothing else. An allow list rather than a check
# for "image/": SVG passes that test and is a document that can carry script,
# not a photograph of a piece.
ALLOWED_PHOTO_MIMETYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/heic",
    "image/heif",
    "image/tiff",
    "image/bmp",
}


class JewelryPhotoUpload(http.Controller):
    """Public, token guarded page used to upload intake photos from a phone.

    Deliberately minimal: it shows the piece and the shots still missing, and
    accepts images. It never exposes the customer, the price or anything else,
    because the link travels by QR on a counter screen where anyone could
    photograph it.
    """

    def _get_repair(self, repair_id, token):
        repair = request.env["repair.order"].sudo().browse(repair_id).exists()
        if not repair or not repair._xb_photo_token_valid(token):
            return False
        return repair

    @http.route(
        "/jewelry/photo/<int:repair_id>/<string:token>",
        type="http", auth="public", website=True, sitemap=False,
    )
    def photo_page(self, repair_id, token, **kw):
        repair = self._get_repair(repair_id, token)
        if not repair:
            return request.render("xb_jewelry_service.photo_link_invalid", {})
        kinds = request.env["xb.jewelry.photo.kind"].sudo().search(
            [("stage", "=", "intake")]
        )
        piece = repair.jewelry_piece_id
        applicable = kinds.filtered(
            lambda k: repair._photo_kind_applies(k, piece)
        )
        return request.render(
            "xb_jewelry_service.photo_link_page",
            {
                "repair": repair,
                "piece": piece,
                "kinds": applicable,
                "taken": {p.kind_id.id: p for p in repair.photo_ids},
                "token": token,
                "company": repair.company_id,
                "uploaded": kw.get("uploaded"),
                "rejected": kw.get("rejected"),
            },
        )

    @http.route(
        "/jewelry/photo/<int:repair_id>/<string:token>/upload",
        type="http", auth="public", methods=["POST"], csrf=True, website=True,
        sitemap=False,
    )
    def photo_upload(self, repair_id, token, **post):
        repair = self._get_repair(repair_id, token)
        if not repair:
            return request.render("xb_jewelry_service.photo_link_invalid", {})

        Photo = request.env["xb.jewelry.photo"].sudo()
        # Only the shots this particular piece is actually asked for. Anything
        # else arriving in the form is somebody poking at the endpoint.
        piece = repair.jewelry_piece_id
        allowed_kinds = request.env["xb.jewelry.photo.kind"].sudo().search(
            [("stage", "=", "intake")]
        ).filtered(lambda k: repair._photo_kind_applies(k, piece))
        allowed_ids = set(allowed_kinds.ids)

        saved = rejected = 0
        for key, upload in request.httprequest.files.items():
            if not key.startswith("kind_") or not upload.filename:
                continue
            try:
                kind_id = int(key.split("_", 1)[1])
            except ValueError:
                continue
            if kind_id not in allowed_ids:
                rejected += 1
                continue
            content = upload.read(MAX_PHOTO_BYTES + 1)
            if not content:
                continue
            if len(content) > MAX_PHOTO_BYTES:
                rejected += 1
                continue
            # The real content decides, not the file name or what the browser
            # claims: an .png header on an HTML payload is the oldest trick
            # there is, and this endpoint is reachable without a login.
            if guess_mimetype(content, default="") not in ALLOWED_PHOTO_MIMETYPES:
                rejected += 1
                continue
            # One photo per kind: a retake replaces, it does not pile up.
            existing = repair.photo_ids.filtered(lambda p: p.kind_id.id == kind_id)
            vals = {"image": base64.b64encode(content)}
            if existing:
                existing[0].write(vals)
            else:
                Photo.create(
                    dict(
                        vals,
                        kind_id=kind_id,
                        repair_id=repair.id,
                        piece_id=repair.jewelry_piece_id.id,
                    )
                )
            saved += 1

        if saved:
            repair.message_post(
                body=_("%(count)s photo(s) uploaded from a phone.", count=saved)
            )
        if rejected:
            repair.message_post(
                body=_(
                    "%(count)s upload(s) were refused: not an image, too large, "
                    "or not a photo this piece is asked for.",
                    count=rejected,
                )
            )
        return request.redirect(
            f"/jewelry/photo/{repair_id}/{token}"
            f"?uploaded={saved}&rejected={rejected}"
        )
