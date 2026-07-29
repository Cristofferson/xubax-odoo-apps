from odoo import fields, models


class ResCompany(models.Model):
    """Templates are picked, never shipped.

    Every WhatsApp template has to be approved by Meta against a specific
    business account, so a module cannot bring its own: the shop selects the
    ones it got approved.
    """

    _inherit = "res.company"

    xb_wa_template_received_id = fields.Many2one(
        "whatsapp.template",
        string="Piece received",
        domain="[('model', '=', 'repair.order')]",
    )
    xb_wa_template_quote_id = fields.Many2one(
        "whatsapp.template",
        string="Quote to authorize",
        domain="[('model', '=', 'repair.order')]",
    )
    xb_wa_template_ready_id = fields.Many2one(
        "whatsapp.template",
        string="Piece ready",
        domain="[('model', '=', 'repair.order')]",
    )
    xb_wa_template_reminder_id = fields.Many2one(
        "whatsapp.template",
        string="Pickup reminder",
        domain="[('model', '=', 'repair.order')]",
    )
    xb_wa_notify_received = fields.Boolean(string="Notify on intake", default=True)
    xb_email_fallback = fields.Boolean(
        string="Fall back to email",
        default=True,
        help="When WhatsApp is not possible, because the customer has no phone "
        "on file or the message fails, write to them instead. The customer just "
        "handed over gold: silence is not an option.",
    )
    xb_wa_notify_ready = fields.Boolean(string="Notify when ready", default=True)
    xb_wa_reminder_days = fields.Char(
        string="Reminder days",
        default="7,15,30",
        help="Days after the piece is ready to remind the customer, "
        "separated by commas. Leave empty to never chase.",
    )

    def _xb_reminder_thresholds(self):
        self.ensure_one()
        days = []
        for chunk in (self.xb_wa_reminder_days or "").split(","):
            chunk = chunk.strip()
            if chunk.isdigit():
                days.append(int(chunk))
        return sorted(days)
