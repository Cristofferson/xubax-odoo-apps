from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class XbMetalPurity(models.Model):
    """Numeric fineness behind each metal attribute value.

    Shops usually keep the karat as free text on the product ("14kt"), which
    is useless for arithmetic. This table turns that label into a number so
    the pure metal weight, and therefore the scrap reconciliation with the
    jeweller, can actually be computed.
    """

    _name = "xb.metal.purity"
    _description = "Metal Purity"
    _order = "purity desc, id"
    _rec_name = "attribute_value_id"

    attribute_value_id = fields.Many2one(
        "product.attribute.value",
        string="Metal",
        required=True,
        ondelete="cascade",
    )
    purity = fields.Float(
        required=True,
        digits=(4, 4),
        help="Fraction of pure metal, between 0 and 1. "
        "For example 18kt gold is 0.7500 and sterling silver is 0.9250.",
    )
    karat = fields.Char(help="Human readable label, e.g. 18kt or 925.")
    is_precious = fields.Boolean(
        default=True,
        help="Uncheck for steel, plated or imitation metals, "
        "where scrap reconciliation makes no sense.",
    )
    active = fields.Boolean(default=True)

    _value_uniq = models.Constraint(
        "unique(attribute_value_id)",
        "Each metal value can only have one purity.",
    )

    @api.constrains("purity")
    def _check_purity(self):
        for record in self:
            if not 0 < record.purity <= 1:
                raise ValidationError(
                    _("Purity must be greater than 0 and at most 1.")
                )
