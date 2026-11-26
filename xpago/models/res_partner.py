from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    xpago_domiciliation_count = fields.Integer(string="Card on file charges", compute='_compute_xpago_domiciliation_count',
                                               groups='account.group_account_invoice')

    def _compute_xpago_domiciliation_count(self):
        counts = dict(self.env['payment.xpago.domiciliation']._read_group(
            [('partner_id', 'in', self.commercial_partner_id.ids)], ['partner_id'], ['__count']))
        for partner in self:
            partner.xpago_domiciliation_count = counts.get(partner.commercial_partner_id, 0)

    def action_view_xpago_domiciliations(self):
        self.ensure_one()
        partner = self.commercial_partner_id
        return {
            'type': 'ir.actions.act_window',
            'name': _("Card on file charges"),
            'res_model': 'payment.xpago.domiciliation',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', partner.id)],
            'context': {'default_partner_id': partner.id},
        }
