from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.xpago.upgrade import fold_old_modules


@tagged('post_install', '-at_install')
class TestFoldOldModules(TransactionCase):
    """A database that had the three former XPago apps keeps their records under the single app."""

    def old_module(self, name):
        Module = self.env['ir.module.module']
        module = Module.search([('name', '=', name)])
        if not module:
            module = Module.create({'name': name, 'shortdesc': name})
        module.state = 'installed'
        return module

    def test_records_settings_and_templates_move_to_the_single_app(self):
        payment = self.old_module('payment_xpago')
        pos = self.old_module('pos_xpago')
        Data = self.env['ir.model.data']
        partner = self.env['res.partner'].create({'name': 'Registro viejo'})
        Data.create({'module': 'payment_xpago', 'name': 'xp_fold_record', 'model': 'res.partner', 'res_id': partner.id})
        Data.create({'module': 'pos_xpago', 'name': 'xp_fold_shared_name', 'model': 'res.partner',
                     'res_id': partner.id})
        view = self.env['ir.ui.view'].create({'name': 'old', 'type': 'qweb', 'key': 'payment_xpago.xp_fold_template',
                                              'arch': '<t t-name="payment_xpago.xp_fold_template"><div/></t>'})
        provider = self.env['payment.provider'].search([('code', '=', 'xpago')], limit=1)
        provider.module_id = payment
        self.env.flush_all()

        bridge = self.old_module('xpago_self_order')
        Data.create({'module': 'xpago_self_order', 'name': 'xp_fold_bridge_record', 'model': 'res.partner',
                     'res_id': partner.id})
        self.env.flush_all()
        with patch('odoo.addons.xpago.upgrade.RENAMED', {('pos_xpago', 'xp_fold_shared_name'): 'xp_fold_shared_name_pos'}):
            fold_old_modules(self.env.cr, 'xpago')
        self.env.invalidate_all()

        self.assertEqual(self.env.ref('xpago.xp_fold_record'), partner)
        self.assertEqual(self.env.ref('xpago.xp_fold_shared_name_pos'), partner,
                         'a name used by two former apps is renamed instead of lost')
        self.assertEqual(self.env.ref('xpago.xp_fold_bridge_record'), partner, 'the former bridges join the app too')
        self.assertFalse(Data.search([('module', 'in', ('payment_xpago', 'pos_xpago', 'xpago_self_order'))]))
        self.assertEqual(view.key, 'xpago.xp_fold_template')
        self.assertEqual((payment.state, pos.state, bridge.state), ('uninstalled', 'uninstalled', 'uninstalled'))
        self.assertEqual(provider.module_id.name, 'xpago')

    def test_nothing_happens_without_the_former_apps(self):
        before = self.env['ir.model.data'].search_count([('module', '=', 'xpago')])
        fold_old_modules(self.env.cr, 'xpago')
        self.assertEqual(self.env['ir.model.data'].search_count([('module', '=', 'xpago')]), before)

    def test_one_app_brings_the_point_of_sale_and_the_kiosk(self):
        xpago = self.env['ir.module.module'].search([('name', '=', 'xpago')])
        self.assertLessEqual({'payment', 'point_of_sale', 'pos_self_order'}, set(xpago.dependencies_id.mapped('name')))
