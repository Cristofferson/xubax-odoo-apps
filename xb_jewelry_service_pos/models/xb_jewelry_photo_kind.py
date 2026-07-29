from odoo import api, models


class XbJewelryPhotoKind(models.Model):
    _name = "xb.jewelry.photo.kind"
    _inherit = ["xb.jewelry.photo.kind", "pos.load.mixin"]

    @api.model
    def _load_pos_data_domain(self, data, config):
        return [("stage", "=", "intake")]

    @api.model
    def _load_pos_data_fields(self, config):
        return ["name", "code", "sequence", "stage", "required", "condition"]
