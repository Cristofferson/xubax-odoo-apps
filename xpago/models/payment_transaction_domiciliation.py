from odoo import fields, models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    xpago_domiciliation_id = fields.Many2one('payment.xpago.domiciliation', string="Card on file charge",
                                             readonly=True, index='btree_not_null', ondelete='set null')

    def _post_process(self):
        # The money is in: stamping or sending the invoice (a subscription renewal sends it right away) must never
        # undo the recorded payment. See account_move_send.py.
        super(PaymentTransaction, self.with_context(xpago_keep_payment=True))._post_process()
        template = self.env.ref('xpago.mail_template_domiciled_charge', raise_if_not_found=False)
        for tx in self.filtered(lambda t: t.state == 'done' and t.xpago_domiciliation_id.notify_customer):
            if template and tx.partner_id.email:
                template.sudo().send_mail(tx.id, email_layout_xmlid='mail.mail_notification_light')
