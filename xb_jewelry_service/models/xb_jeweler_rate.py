from odoo import api, fields, models


class XbJewelerRate(models.Model):
    """What each jeweler charges for each job.

    The rate is a default, never a lock: the price of a given piece can always
    be argued at the counter and typed over on the repair order itself.
    """

    _name = "xb.jeweler.rate"
    _description = "Jeweler Rate"
    _order = "partner_id, product_id"

    partner_id = fields.Many2one(
        "res.partner",
        string="Jeweler",
        required=True,
        ondelete="cascade",
        domain="[('is_jeweler', '=', True)]",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Job",
        required=True,
        domain="[('type', '=', 'service')]",
    )
    price = fields.Monetary(required=True, currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company
    )
    date_from = fields.Date(
        help="Optional. Leave empty for a rate that is always valid."
    )
    active = fields.Boolean(default=True)

    _rate_uniq = models.Constraint(
        "unique(partner_id, product_id, company_id)",
        "This jeweler already has a rate for that job.",
    )

    @api.model
    def _get_rate(self, partner, product, company):
        if not partner or not product:
            return 0.0
        rate = self.search(
            [
                ("partner_id", "=", partner.id),
                ("product_id", "=", product.id),
                ("company_id", "in", [company.id, False]),
            ],
            limit=1,
        )
        return rate.price
