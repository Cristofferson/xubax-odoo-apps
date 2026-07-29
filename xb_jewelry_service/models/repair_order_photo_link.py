import secrets
from datetime import timedelta

from odoo import _, fields, models


class RepairOrder(models.Model):
    """Short lived link so photos can be taken with a phone.

    Registers differ: a tablet has a camera, the desktop at the back does not.
    Rather than force a workflow on the shop, the counter can hand the job to
    whatever phone is nearby, and the link dies on its own.
    """

    _inherit = "repair.order"

    xb_photo_token = fields.Char(copy=False, index=True, groups="base.group_user")
    xb_photo_token_expiry = fields.Datetime(copy=False, groups="base.group_user")

    def xb_generate_photo_link(self):
        """Mint a fresh token and return the URL to open on the phone."""
        self.ensure_one()
        minutes = (
            self.company_id or self.env.company
        ).xb_photo_link_minutes or 30
        token = secrets.token_urlsafe(24)
        self.sudo().write(
            {
                "xb_photo_token": token,
                "xb_photo_token_expiry": fields.Datetime.now()
                + timedelta(minutes=minutes),
            }
        )
        url = f"{self.get_base_url()}/jewelry/photo/{self.id}/{token}"
        return {
            "url": url,
            "qr": f"/report/barcode/?barcode_type=QR&value={url}&width=300&height=300",
            "minutes": minutes,
        }

    def _xb_photo_token_valid(self, token):
        """Constant-time check, plus expiry. Never trust the id alone."""
        self.ensure_one()
        stored = self.sudo().xb_photo_token
        expiry = self.sudo().xb_photo_token_expiry
        if not stored or not token:
            return False
        if not secrets.compare_digest(stored, token):
            return False
        if not expiry or expiry < fields.Datetime.now():
            return False
        return True

    def xb_revoke_photo_link(self):
        self.sudo().write({"xb_photo_token": False, "xb_photo_token_expiry": False})
        return True

    def action_xb_photo_link(self):
        """Show the link from the back office too, not only from the POS."""
        self.ensure_one()
        data = self.xb_generate_photo_link()
        self.message_post(
            body=_(
                "A photo upload link was generated, valid for %(min)s minutes.",
                min=data["minutes"],
            )
        )
        return {
            "type": "ir.actions.act_url",
            "url": data["url"],
            "target": "new",
        }
