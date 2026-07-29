from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    xb_metal_attribute_id = fields.Many2one(
        "product.attribute",
        string="Metal attribute",
        help="The product attribute this shop already uses for metal and "
        "karat. Intake reuses its values instead of a parallel list.",
    )
    xb_size_attribute_id = fields.Many2one(
        "product.attribute",
        string="Size attribute",
        help="The product attribute this shop already uses for ring sizes. "
        "Intake reuses its values instead of a free text box.",
    )
    xb_intake_photo_policy = fields.Selection(
        [
            ("none", "None while the customer waits"),
            ("min", "Only the main shot"),
            ("all", "Every shot that applies"),
        ],
        string="Photos required at intake",
        default="none",
        required=True,
        help="How much photography the counter has to do with the customer "
        "standing there. Whatever is chosen, the piece still cannot go to the "
        "workshop until every applicable photo exists: this setting only "
        "decides how long the customer waits, never whether the evidence is "
        "eventually taken.",
    )
    xb_intake_main_photo_kind_id = fields.Many2one(
        "xb.jewelry.photo.kind",
        string="Main intake photo",
        domain="[('stage', '=', 'intake')]",
        help="The single shot asked for when only the main one is required.",
    )

    def _xb_intake_required_kinds(self, applicable_kinds):
        """Which of the applicable shots are demanded at the counter."""
        self.ensure_one()
        if self.xb_intake_photo_policy == "none":
            return applicable_kinds.browse()
        if self.xb_intake_photo_policy == "min":
            main = self.xb_intake_main_photo_kind_id
            if not main:
                # Falling back to the first one in the checklist is kinder than
                # asking for nothing when the shop asked for something.
                return applicable_kinds[:1]
            return applicable_kinds.filtered(lambda k: k == main)
        return applicable_kinds.filtered("required")

    xb_scrap_tolerance = fields.Float(
        string="Scrap tolerance (%)",
        default=10.0,
        help="Accepted loss on metal handed to a jeweler.",
    )
    xb_warranty_days = fields.Integer(string="Warranty (days)", default=90)
    xb_require_intake_signature = fields.Boolean(
        string="Signature on intake", default=True
    )
    xb_require_dispatch_signature = fields.Boolean(
        string="Signature on workshop dispatch", default=True
    )
    xb_require_delivery_signature = fields.Boolean(
        string="Signature on delivery", default=True
    )
    xb_delivery_balance_policy = fields.Selection(
        [
            ("none", "Hand the piece over anyway"),
            ("warn", "Warn the counter, let it through"),
            ("block", "Refuse until the balance is settled"),
        ],
        string="Unpaid balance on delivery",
        default="warn",
        required=True,
        help="What to do when a finished piece is collected while the customer "
        "still owes money on it. The signature only proves who took the piece, "
        "never that it was paid for, so the two are checked separately.",
    )
    xb_custody_location_id = fields.Many2one(
        "stock.location",
        string="Custody location",
        domain="[('usage', '=', 'internal')]",
    )
    xb_photo_link_minutes = fields.Integer(
        string="Photo link validity (min)",
        default=30,
        help="How long the QR link to upload photos from a phone stays alive.",
    )
    xb_intake_terms = fields.Html(
        string="Intake terms",
        translate=True,
        help="Printed on the receipt the customer signs when leaving a piece. "
        "Have it reviewed by your lawyer: this is what protects you if the "
        "customer later disputes the condition the piece was in.",
        default=lambda self: self._default_intake_terms(),
    )
    xb_delivery_terms = fields.Html(
        string="Delivery terms",
        translate=True,
        default=lambda self: self._default_delivery_terms(),
    )
    xb_unclaimed_days = fields.Integer(
        string="Unclaimed after (days)",
        default=90,
        help="Days after the piece is ready before it counts as unclaimed.",
    )

    def _default_intake_terms(self):
        return (
            "<p>The customer leaves the piece described above for service, and "
            "agrees that its condition, weight and photographs recorded at this "
            "moment are the reference for its return. Review and adapt this text "
            "with your legal advisor.</p>"
        )

    def _default_delivery_terms(self):
        return (
            "<p>The customer receives the piece and confirms it matches the "
            "agreed work. Review and adapt this text with your legal advisor.</p>"
        )

    xb_jeweler_service_product_id = fields.Many2one(
        "product.product",
        string="Jeweler service product",
        domain="[('type', '=', 'service')]",
        help="Fallback product used on vendor bills when a job has no "
        "service product of its own.",
    )
    xb_custody_product_id = fields.Many2one(
        "product.product",
        string="Custody product",
        help="Generic serial-tracked product used to trace customer pieces "
        "through Inventory. Keep its cost at zero.",
    )
