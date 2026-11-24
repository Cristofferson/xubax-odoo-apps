# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Related fields bound to the currently selected Point of Sale (pos_config_id).
    # This is the standard Odoo pattern for surfacing pos.config options in the
    # Settings > Point of Sale screen.
    pos_xb_enable_sale_order = fields.Boolean(
        related="pos_config_id.xb_enable_sale_order", readonly=False
    )
    pos_xb_allow_quotation = fields.Boolean(
        related="pos_config_id.xb_allow_quotation", readonly=False
    )
    pos_xb_differentiate_order_layaway = fields.Boolean(
        related="pos_config_id.xb_differentiate_order_layaway", readonly=False
    )
    pos_xb_default_so_state = fields.Selection(
        related="pos_config_id.xb_default_so_state", readonly=False
    )
    pos_xb_show_order_balance = fields.Boolean(
        related="pos_config_id.xb_show_order_balance", readonly=False
    )
    pos_xb_enrich_receipt = fields.Boolean(
        related="pos_config_id.xb_enrich_receipt", readonly=False
    )
    pos_xb_show_partner_ref = fields.Boolean(
        related="pos_config_id.xb_show_partner_ref", readonly=False
    )
    pos_xb_autoprint_on_create = fields.Boolean(
        related="pos_config_id.xb_autoprint_on_create", readonly=False
    )
    pos_xb_duplicate_receipt_on_create = fields.Boolean(
        related="pos_config_id.xb_duplicate_receipt_on_create", readonly=False
    )
    pos_xb_ask_quotation_delivery = fields.Boolean(
        related="pos_config_id.xb_ask_quotation_delivery", readonly=False
    )
    pos_xb_list_until_delivered = fields.Boolean(
        related="pos_config_id.xb_list_until_delivered", readonly=False
    )
    pos_xb_show_portal_link = fields.Boolean(
        related="pos_config_id.xb_show_portal_link", readonly=False
    )
    pos_xb_autofactura_qr_paid_only = fields.Boolean(
        related="pos_config_id.xb_autofactura_qr_paid_only", readonly=False
    )
    pos_xb_rounding_product_id = fields.Many2one(
        related="pos_config_id.xb_rounding_product_id", readonly=False
    )
    # Document templates per kind -- bound to the current COMPANY (not the PoS), so the
    # validity/terms differ by document type for the whole company. res.config.settings
    # already carries company_id.
    xb_quotation_template_id = fields.Many2one(
        related="company_id.xb_quotation_template_id", readonly=False
    )
    xb_order_template_id = fields.Many2one(
        related="company_id.xb_order_template_id", readonly=False
    )
    xb_layaway_template_id = fields.Many2one(
        related="company_id.xb_layaway_template_id", readonly=False
    )
    # Layaway terms, per company.
    xb_layaway_days = fields.Integer(related="company_id.xb_layaway_days", readonly=False)
    xb_layaway_down_percent = fields.Float(
        related="company_id.xb_layaway_down_percent", readonly=False)
    xb_layaway_min_payment = fields.Monetary(
        related="company_id.xb_layaway_min_payment", readonly=False)
    xb_layaway_cancel_fee_percent = fields.Float(
        related="company_id.xb_layaway_cancel_fee_percent", readonly=False)
    xb_layaway_notify_customer = fields.Boolean(
        related="company_id.xb_layaway_notify_customer", readonly=False)
    xb_order_down_percent = fields.Float(related="company_id.xb_order_down_percent", readonly=False)
    xb_layaway_warn_reserved = fields.Boolean(
        related="company_id.xb_layaway_warn_reserved", readonly=False)

    def action_xb_order_reminder_rule(self):
        return self._xb_open_rule("xb_sale_order_from_pos.automation_order_reminder")

    def action_xb_layaway_reminder_rule(self):
        return self._xb_open_rule("xb_sale_order_from_pos.automation_layaway_reminder")

    def _xb_open_rule(self, xmlid):
        """Open an automation rule of this module (the reminders before a date)."""
        rule = self.env.ref(xmlid, raise_if_not_found=False)
        if not rule:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "base.automation",
            "res_id": rule.id,
            "view_mode": "form",
            "target": "current",
        }
