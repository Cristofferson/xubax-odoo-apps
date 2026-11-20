from odoo.tests import TransactionCase, tagged

from odoo.addons.xb_price_checker import manual


@tagged('post_install', '-at_install')
class TestManual(TransactionCase):
    """The manual lands in Knowledge (Articles) in the shop's language, and only where Knowledge exists."""

    def test_without_knowledge_nothing_breaks(self):
        if 'knowledge.article' in self.env:
            self.skipTest('Knowledge is installed here')
        self.assertFalse(manual.install_manual(self.env))

    def test_manual_in_spanish(self):
        if 'knowledge.article' not in self.env:
            self.skipTest('Knowledge is not installed here')
        old = self.env.ref(manual.ARTICLE_XMLID, raise_if_not_found=False)
        if old:
            self.env['ir.model.data'].search([('module', '=', 'xb_price_checker'), ('name', '=', 'article_manual')]).unlink()
            old.unlink()
        self.env['res.lang']._activate_lang('es_MX')
        self.env.ref('base.user_admin').lang = 'es_MX'
        article = manual.install_manual(self.env)
        self.assertEqual(article, self.env.ref(manual.ARTICLE_XMLID))
        self.assertEqual(article.name, 'Verificador de precios: manual')
        self.assertIn('Qué es', article.body)
        self.assertIn('Problemas comunes', article.body)
        self.assertIn('/xb_price_checker/static/src/img/manual/terminal.jpg', article.body)
        self.assertNotIn('What it is', article.body)

        # A manual someone edited is theirs: an upgrade does not overwrite it.
        user = self.env['res.users'].create({
            'name': 'Gerente', 'login': 'xpc_manual_editor',
            'group_ids' if 'group_ids' in self.env['res.users']._fields else 'groups_id':
                [(4, self.env.ref('base.group_user').id)]})
        article.with_user(user).sudo().write({'body': '<p>Nuestras notas</p>'})
        self.env.ref(manual.ARTICLE_XMLID).invalidate_recordset()
        manual.install_manual(self.env)
        self.assertIn('Nuestras notas', article.body)
