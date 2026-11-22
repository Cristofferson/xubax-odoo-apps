import logging

from markupsafe import Markup

from odoo import _, api, models

_logger = logging.getLogger(__name__)


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _generate_and_send_invoices(self, moves, from_cron=False, allow_raising=True, allow_fallback_pdf=False,
                                    **custom_settings):
        if not self.env.context.get('xpago_keep_payment'):
            return super()._generate_and_send_invoices(moves, from_cron=from_cron, allow_raising=allow_raising,
                                                       allow_fallback_pdf=allow_fallback_pdf, **custom_settings)
        # After a card payment: a stamping or sending problem is noted on the invoice, never raised.
        try:
            with self.env.cr.savepoint():
                return super()._generate_and_send_invoices(moves, from_cron=from_cron, allow_raising=False,
                                                           allow_fallback_pdf=allow_fallback_pdf, **custom_settings)
        except Exception as error:  # noqa: BLE001 - whatever fails here, the payment stays recorded
            _logger.warning("Invoices %s paid but not sent: %s", moves.ids, error)
            for move in moves:
                move.message_post(body=Markup("%s<br/>%s") % (
                    _("The payment was recorded, but the invoice could not be stamped or sent:"), str(error)))
            self._xpago_todo_send(moves)
            return {}

    @api.model
    def _hook_if_errors(self, moves_data, allow_raising=True):
        result = super()._hook_if_errors(moves_data, allow_raising=allow_raising)
        if self.env.context.get('xpago_keep_payment'):
            self._xpago_todo_send(self.env['account.move'].union(*[move.sudo() for move in moves_data]))
        return result

    @api.model
    def _xpago_todo_send(self, moves):
        """Someone has to stamp and send by hand an invoice the customer already paid."""
        for move in moves:
            move.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_("Stamp and send this paid invoice"),
                note=_("The card was charged and the payment is recorded. Fix the problem written on the invoice and "
                       "send it from «Send»."),
                user_id=(move.invoice_user_id or move.create_uid or self.env.user).id,
            )
