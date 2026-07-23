# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class XbBillProductImage(models.Model):
    _name = 'xb.bill.product.image'
    _description = "Candidate Image for a Product"
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    proposal_id = fields.Many2one(
        comodel_name='xb.bill.product.proposal',
        string="Proposal",
        ondelete='cascade',
        index=True,
    )
    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string="Product",
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string="Title")
    url = fields.Char(string="Source URL", required=True)
    source = fields.Char(string="Found on")
    width = fields.Integer()
    height = fields.Integer()
    image_1920 = fields.Image(max_width=1920, max_height=1920)

    def action_choose(self):
        """Use this candidate, and drop the others."""
        self.ensure_one()
        if not self.image_1920:
            raise UserError(_("This candidate could not be downloaded."))
        if self.proposal_id:
            self.proposal_id.write({
                'image_1920': self.image_1920,
                'image_state': 'done',
            })
            if self.proposal_id.product_id:
                self.proposal_id.product_id.product_tmpl_id.sudo().write({
                    'image_1920': self.image_1920,
                    'xb_vbp_image_state': 'done',
                })
            siblings = self.proposal_id.image_candidate_ids - self
        elif self.product_tmpl_id:
            self.product_tmpl_id.sudo().write({
                'image_1920': self.image_1920,
                'xb_vbp_image_state': 'done',
            })
            siblings = self.product_tmpl_id.xb_vbp_image_candidate_ids - self
        else:
            siblings = self.browse()
        siblings.unlink()
        return True
