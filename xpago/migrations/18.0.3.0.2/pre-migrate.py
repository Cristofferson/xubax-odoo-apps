from odoo.addons.xpago.upgrade import fold_old_modules

# Views of «XPago: Mexico» for the deposit accounts that the payment rules now decide alone.
GONE_VIEWS = ('l10n_mx_payment_provider_form', 'view_move_form', 'view_order_form')


def migrate(cr, version):
    # The models it only extended for an account written by hand on an order or invoice stay with their own apps.
    cr.execute("""DELETE FROM ir_model_data WHERE module = 'xpago_l10n_mx' AND model = 'ir.model'
                   AND name IN ('model_account_move', 'model_sale_order')""")
    fold_old_modules(cr, 'xpago')
    cr.execute("""
        DELETE FROM ir_ui_view WHERE id IN (
            SELECT res_id FROM ir_model_data WHERE module = 'xpago' AND model = 'ir.ui.view' AND name IN %s)
    """, [GONE_VIEWS])
    cr.execute("DELETE FROM ir_model_data WHERE module = 'xpago' AND model = 'ir.ui.view' AND name IN %s", [GONE_VIEWS])
