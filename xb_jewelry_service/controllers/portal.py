from odoo import _, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class JewelryPortal(CustomerPortal):
    """Lets the owner see their own pieces.

    The customer is the one person who cannot walk into the safe, so the file
    of their piece, with the photos taken before and after, is what tells them
    the work was done and the piece is the same one they left.
    """

    def _jewelry_domain(self):
        partner = request.env.user.partner_id
        return [("partner_id", "child_of", partner.commercial_partner_id.id)]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "jewelry_count" in counters:
            values["jewelry_count"] = request.env["xb.jewelry.piece"].search_count(
                self._jewelry_domain()
            )
        return values

    @http.route(
        ["/my/jewelry", "/my/jewelry/page/<int:page>"],
        type="http", auth="user", website=True,
    )
    def portal_my_jewelry(self, page=1, sortby="date", **kw):
        Piece = request.env["xb.jewelry.piece"]
        domain = self._jewelry_domain()

        sortings = {
            "date": {"label": _("Newest"), "order": "id desc"},
            "name": {"label": _("Reference"), "order": "name"},
            "state": {"label": _("Status"), "order": "custody_state"},
        }
        order = sortings.get(sortby, sortings["date"])["order"]

        total = Piece.search_count(domain)
        pager = portal_pager(
            url="/my/jewelry",
            url_args={"sortby": sortby},
            total=total,
            page=page,
            step=self._items_per_page,
        )
        pieces = Piece.search(
            domain, order=order, limit=self._items_per_page, offset=pager["offset"]
        )
        return request.render(
            "xb_jewelry_service.portal_my_jewelry",
            {
                "pieces": pieces,
                "page_name": "jewelry",
                "pager": pager,
                "default_url": "/my/jewelry",
                "sortby": sortby,
                "searchbar_sortings": sortings,
            },
        )

    @http.route(["/my/jewelry/<int:piece_id>"], type="http", auth="public", website=True)
    def portal_jewelry_detail(self, piece_id, access_token=None, **kw):
        try:
            piece_sudo = self._document_check_access(
                "xb.jewelry.piece", piece_id, access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        return request.render(
            "xb_jewelry_service.portal_jewelry_detail",
            {
                "piece": piece_sudo,
                "page_name": "jewelry",
                "intake_photos": piece_sudo.photo_ids.filtered(
                    lambda p: p.stage == "intake"
                ),
                "after_photos": piece_sudo.photo_ids.filtered(
                    lambda p: p.stage == "after"
                ),
                "token": access_token,
            },
        )
