from odoo.addons.payment.tests.common import PaymentCommon


class XpagoCommon(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency = cls.env.ref('base.MXN')
        cls.currency.active = True
        cls.provider = cls._prepare_provider('xpago', update_values={'xpago_api_key': 'xpk_test_key'})
        cls.checkout_id = 'chk-123'
        cls.checkout = {'id': cls.checkout_id, 'checkout_url': 'https://pay.example.com/checkout/chk-123?lang=es'}

    def payment_data(self, status='paid', **extra):
        return {'id': self.checkout_id, 'status': status, 'amount': self.amount,
                'currency': 'MXN', 'reference': self.reference, **extra}
