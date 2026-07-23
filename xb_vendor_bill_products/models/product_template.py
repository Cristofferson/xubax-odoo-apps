# -*- coding: utf-8 -*-
from odoo import _, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    xb_vbp_auto_created = fields.Boolean(
        string="Created from a vendor bill",
        copy=False,
        readonly=True,
    )
    xb_vbp_origin_move_id = fields.Many2one(
        comodel_name='account.move',
        string="Originating bill",
        copy=False,
        readonly=True,
        ondelete='set null',
    )
    xb_vbp_image_state = fields.Selection(
        selection=[
            ('pending', "Searching"),
            ('proposed', "Candidates found"),
            ('done', "Image set"),
            ('failed', "Nothing found"),
        ],
        string="Image search",
        copy=False,
        readonly=True,
    )
    xb_vbp_image_candidate_ids = fields.One2many(
        comodel_name='xb.bill.product.image',
        inverse_name='product_tmpl_id',
        string="Image candidates",
    )
    xb_vbp_image_candidate_count = fields.Integer(
        compute='_compute_xb_vbp_image_candidate_count')

    def _compute_xb_vbp_image_candidate_count(self):
        counts = dict(self.env['xb.bill.product.image']._read_group(
            [('product_tmpl_id', 'in', self.ids)],
            groupby=['product_tmpl_id'],
            aggregates=['__count'],
        ))
        for template in self:
            template.xb_vbp_image_candidate_count = counts.get(template, 0)

    def action_xb_vbp_search_images(self):
        """Look for pictures now, for the selected products."""
        self.env['xb.product.image.finder']._fill_candidates_for_templates(
            self, force=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'message': _("Image search finished."),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_xb_vbp_view_image_candidates(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Image candidates"),
            'res_model': 'xb.bill.product.image',
            'view_mode': 'kanban,list',
            'domain': [('product_tmpl_id', '=', self.id)],
            'context': {'default_product_tmpl_id': self.id},
        }
