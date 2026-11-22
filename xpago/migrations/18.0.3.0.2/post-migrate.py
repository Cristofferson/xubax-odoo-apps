from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """The accounts «for sales with invoice» and «for the other sales» of the XPago provider become two payment
    rules at the end of the list, so the payment rules are the only place that decides the deposit account."""
    cr.execute("""SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'payment_provider' AND column_name = 'xpago_invoice_bank_account_id'""")
    if not cr.fetchone():
        return
    cr.execute("""SELECT id, company_id, xpago_invoice_bank_account_id, xpago_other_bank_account_id FROM payment_provider
                   WHERE code = 'xpago' AND (xpago_invoice_bank_account_id IS NOT NULL
                                             OR xpago_other_bank_account_id IS NOT NULL)""")
    env = api.Environment(cr, SUPERUSER_ID, {'lang': 'es_MX'})
    Rule = env['payment.xpago.rule'].with_context(active_test=False)
    Account = env['payment.xpago.bank.account'].with_context(active_test=False)
    for _provider_id, company_id, invoice_account, other_account in cr.fetchall():
        for sequence, mode, account_id, name in (
                (1000, 'invoiced', invoice_account, "Ventas con factura timbrada"),
                (1001, 'public', other_account, "Ventas sin factura (público en general)")):
            account = Account.browse(account_id).exists()
            if not account or Rule.search_count([('company_id', '=', company_id), ('invoice_mode', '=', mode),
                                                 ('bank_account_id', '=', account.id)]):
                continue
            Rule.create({'name': name, 'sequence': sequence, 'company_id': company_id, 'invoice_mode': mode,
                         'bank_account_id': account.id, 'msi_mode': 'keep', 'use_online': True,
                         'use_pos': True, 'use_kiosk': True})
