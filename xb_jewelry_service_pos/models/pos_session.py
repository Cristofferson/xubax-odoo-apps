from odoo import api, models


class PosSession(models.Model):
    _inherit = "pos.session"

    @api.model
    def _load_pos_data_models(self, config):
        data = super()._load_pos_data_models(config)
        # Only the photo checklist is preloaded: it is a handful of records and
        # the intake wizard needs it on every piece. Service orders are NOT
        # preloaded on purpose, they are fetched on demand so the session
        # payload does not grow with the workshop backlog.
        data += ["xb.jewelry.photo.kind"]
        return data
