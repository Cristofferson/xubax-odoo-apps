# -*- coding: utf-8 -*-
from odoo import fields, models


class XbVaAvatar(models.Model):
    """A face for the virtual seller: a picture and, for full screen, a picture or videos."""
    _name = "xb.va.avatar"
    _description = "Virtual seller avatar"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    gender = fields.Selection([("female", "Woman"), ("male", "Man")], required=True, default="female")
    image = fields.Image("Face", max_width=512, max_height=512, required=True,
                         help="Square, face centered: shown in the round button and the chat.")
    image_full = fields.Image("Full screen picture", max_width=1080, max_height=1920,
                              help="Vertical, from the head to the waist: shown when the seller fills the screen.")
    video_idle = fields.Binary("Video: listening", attachment=True,
                               help="Short MP4 loop of the person listening (breathing, blinking, smiling). Optional.")
    video_talk = fields.Binary("Video: talking", attachment=True,
                               help="Short MP4 loop of the person talking. Played while the seller speaks. Optional.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", help="Empty = every company can use it.")

    def _xb_va_payload(self):
        self.ensure_one()
        return {
            "face": bool(self.image),
            "full": bool(self.image_full),
            "idle": bool(self.video_idle),
            "talk": bool(self.video_talk),
            "stamp": fields.Datetime.to_string(self.write_date),
        }
