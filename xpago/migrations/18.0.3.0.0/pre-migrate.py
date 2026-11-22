from odoo.addons.xpago.upgrade import fold_old_modules

# Views of the folded apps that the single app does not have any more.
GONE_VIEWS = ('subscription_payment_xpago_domiciliation_view_form', 'calculator_res_config_settings_view_form')


def migrate(cr, version):
    # Card on file charges, the calculator and the subscription fix join the app: their records stay as they were.
    fold_old_modules(cr, 'xpago')
    cr.execute("""
        DELETE FROM ir_ui_view WHERE id IN (
            SELECT res_id FROM ir_model_data WHERE module = 'xpago' AND model = 'ir.ui.view' AND name IN %s)
    """, [GONE_VIEWS])
    cr.execute("DELETE FROM ir_model_data WHERE module = 'xpago' AND model = 'ir.ui.view' AND name IN %s", [GONE_VIEWS])
