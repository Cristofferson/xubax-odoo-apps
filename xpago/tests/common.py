from odoo.addons.payment.tests.common import PaymentCommon


class XpagoCommon(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The tests apply XPago's answers for real; the post-processing (accounting) stays skipped.
        cls.enable_process_patcher = False
        cls.currency = cls.env.ref('base.MXN')
        cls.currency.active = True
        cls.provider = cls._prepare_provider('xpago', update_values={'xpago_api_key': 'xpk_test_key'})
        # Odoo 20 keeps the payment methods per provider: pay with XPago's own card method.
        cls.payment_method = cls.provider.payment_method_ids.filtered(lambda m: m.code == 'card')
        cls.payment_method_id = cls.payment_method.id
        cls.checkout_id = 'chk-123'
        cls.checkout = {'id': cls.checkout_id, 'checkout_url': 'https://pay.example.com/checkout/chk-123?lang=es'}

    @staticmethod
    def safe(tx):
        """The transaction as the payment flows write it (Odoo 20 refuses other writes)."""
        return tx.with_context(payment_safe_write=True)

    def payment_data(self, status='paid', **extra):
        return {'id': self.checkout_id, 'status': status, 'amount': self.amount,
                'currency': 'MXN', 'reference': self.reference, **extra}
