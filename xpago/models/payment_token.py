import logging

from odoo import models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentToken(models.Model):
    _inherit = 'payment.token'

    def _handle_archiving(self):
        """Revoke the card in XPago when its token is archived, so it can never be charged again."""
        super()._handle_archiving()
        for token in self.filtered(lambda t: t.provider_code == 'xpago' and t.provider_ref):
            try:
                token.provider_id._xpago_make_request('DELETE', f'/v1/saved-cards/{token.provider_ref}')
            except ValidationError as error:
                # Archiving must go through even when XPago cannot be reached; the card stays unusable here.
                _logger.warning("XPago: could not revoke the saved card %s: %s", token.provider_ref, error)
