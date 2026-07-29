from odoo import fields, models


class XbJewelryPhotoKind(models.Model):
    """Configurable catalogue of the photos a piece must have.

    Shops differ on what they document, so the required shot list is data,
    not code: a jeweller in another country can drop 'Hallmark' and add
    'Certificate' without touching the module.
    """

    _name = "xb.jewelry.photo.kind"
    _description = "Jewelry Photo Kind"
    _order = "stage, sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Technical identifier, used by the Point of Sale screens.",
    )
    sequence = fields.Integer(default=10)
    stage = fields.Selection(
        [
            ("design", "Design reference"),
            ("intake", "Intake"),
            ("after", "After the work"),
        ],
        required=True,
        default="intake",
        help="Design photos are what the customer wants made, shown at the "
        "counter for a commission. Intake photos are the piece as it was "
        "received, and 'after' photos the finished work.",
    )
    required = fields.Boolean(
        default=True,
        help="A required photo blocks the piece from moving forward "
        "until it has been taken.",
    )
    condition = fields.Selection(
        [
            ("always", "Always"),
            ("ring", "Rings only"),
            ("chain", "Chains and bracelets only"),
            ("diamond", "Pieces with diamonds only"),
            ("diamond_laser", "Diamonds with a laser inscription only"),
        ],
        default="always",
        required=True,
        help="Only ask for this photo when the piece matches the condition.",
    )
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        "unique(code)",
        "The photo kind code must be unique.",
    )
