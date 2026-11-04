from odoo.addons.payment.tests.common import PaymentCommon


class XpagoCommon(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency = cls.env.ref('base.MXN')
        cls.currency.active = True
        cls.provider = cls._prepare_provider('xpago', update_values={'xpago_api_key': 'xp_test_key'})
        cls.checkout_id = 'otp-123'
        cls.checkout = {'id': cls.checkout_id, 'redirectUrl': 'https://pay.example.com/checkout/otp-123?lang=es'}

    def payment_data(self, status='CONFIRMED', **extra):
        return {'id': self.checkout_id, 'status': status, 'expired': False, 'amount': self.amount,
                'currency': 'MXN', 'externalId': self.reference, **extra}
