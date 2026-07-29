from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    xb_wa_template_received_id = fields.Many2one(
        related="company_id.xb_wa_template_received_id", readonly=False
    )
    xb_wa_template_quote_id = fields.Many2one(
        related="company_id.xb_wa_template_quote_id", readonly=False
    )
    xb_wa_template_ready_id = fields.Many2one(
        related="company_id.xb_wa_template_ready_id", readonly=False
    )
    xb_wa_template_reminder_id = fields.Many2one(
        related="company_id.xb_wa_template_reminder_id", readonly=False
    )
    xb_wa_notify_received = fields.Boolean(
        related="company_id.xb_wa_notify_received", readonly=False
    )
    xb_wa_notify_ready = fields.Boolean(
        related="company_id.xb_wa_notify_ready", readonly=False
    )
    xb_wa_reminder_days = fields.Char(
        related="company_id.xb_wa_reminder_days", readonly=False
    )
    xb_email_fallback = fields.Boolean(
        related="company_id.xb_email_fallback", readonly=False
    )
