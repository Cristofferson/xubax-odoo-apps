from odoo import api, fields, models


class XbJewelryPhoto(models.Model):
    _name = "xb.jewelry.photo"
    _description = "Jewelry Photo"
    _order = "stage, sequence, id"

    kind_id = fields.Many2one(
        "xb.jewelry.photo.kind",
        string="Kind",
        required=True,
        ondelete="restrict",
    )
    stage = fields.Selection(related="kind_id.stage", store=True)
    sequence = fields.Integer(related="kind_id.sequence", store=True)
    image = fields.Image(required=True, max_width=1920, max_height=1920)
    piece_id = fields.Many2one("xb.jewelry.piece", ondelete="cascade", index=True)
    repair_id = fields.Many2one("repair.order", ondelete="cascade", index=True)
    user_id = fields.Many2one(
        "res.users",
        string="Taken by",
        default=lambda self: self.env.user,
        readonly=True,
    )
    date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    note = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        photos = super().create(vals_list)
        # A photo taken against a repair belongs to the piece for good: the
        # repair is closed and archived one day, the piece file is forever.
        for photo in photos:
            if photo.repair_id and not photo.piece_id:
                photo.piece_id = photo.repair_id.jewelry_piece_id
        return photos
