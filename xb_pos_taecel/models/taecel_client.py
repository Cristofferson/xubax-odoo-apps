# -*- coding: utf-8 -*-
"""Thin transport layer for the TAECEL REST API.

The only place in the module that knows about HTTP. Models call the public
methods and get plain dicts back; nothing above this file deals with status
codes, form encoding or TAECEL's response envelope.

Design note: every call returns a ``TaecelResult`` instead of raising on a
business failure. A declined recharge is a normal outcome the cashier must see,
not an exception -- exceptions are reserved for transport problems.

Methods are grouped by provenance:
    * CONFIRMED -- getProducts / getSales / RegistroCuenta, documented in the
      manual we hold.
    * PENDING   -- request_txn / status_txn / get_balance, the transactional
      API TAECEL issues separately. Kept here so the models compile and the
      shape is ready, but NOT called from the POS until the doc is verified.
"""
import logging
import re
import requests

from odoo import _
from odoo.exceptions import UserError

from .. import const

_logger = logging.getLogger(__name__)


class TaecelResult:
    """Outcome of one API call."""

    def __init__(self, ok, data=None, message='', raw=None, timed_out=False):
        self.ok = ok
        self.data = data if data is not None else {}
        self.message = message or ''
        self.raw = raw
        self.timed_out = timed_out

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return '<TaecelResult %s %s>' % ('ok' if self.ok else 'ko', self.message)


class TaecelClient:

    def __init__(self, base_url, key, nip, timeout=const.DEFAULT_TIMEOUT):
        if not (base_url and key and nip):
            raise UserError(_('The recharges account is missing its URL, key or NIP.'))
        self.base_url = base_url.rstrip('/')
        self.key = key
        self.nip = nip
        self.timeout = timeout or const.DEFAULT_TIMEOUT

    # -- low level ---------------------------------------------------------
    def _post(self, path, payload=None):
        url = '%s/%s' % (self.base_url, path)
        body = dict(payload or {})
        body[const.PARAM_KEY] = self.key
        body[const.PARAM_NIP] = self.nip

        try:
            response = requests.post(url, data=body, timeout=self.timeout)
        except requests.Timeout:
            # Never a failure: TAECEL may well have dispatched. The caller
            # parks it for the reconciler.
            _logger.warning('TAECEL timeout on %s after %ss', path, self.timeout)
            return TaecelResult(False, message=_('The provider did not answer in time.'),
                                timed_out=True)
        except requests.RequestException as err:
            _logger.warning('TAECEL transport error on %s: %s', path, err)
            return TaecelResult(False, message=_('Could not reach the provider: %s', err))

        try:
            parsed = response.json()
        except ValueError:
            snippet = (response.text or '')[:200]
            _logger.warning('TAECEL non-JSON answer on %s: %s', path, snippet)
            return TaecelResult(False, message=_('Unreadable answer from the provider.'),
                                raw=snippet)

        ok = bool(parsed.get(const.RESP_SUCCESS))
        return TaecelResult(
            ok,
            data=parsed.get(const.RESP_DATA),
            message=parsed.get(const.RESP_MESSAGE) or '',
            raw=parsed,
        )

    # == CONFIRMED endpoints ==============================================
    def get_products(self):
        """Full catalog: bolsas, carriers (+input field specs), products."""
        return self._post(const.PATH_PRODUCTS)

    def get_sales(self, fecha, bolsa):
        """Sales history for a day and a wallet.

        ``fecha`` is 'YYYY-MM-DD', ``bolsa`` the wallet id ('1'/'2'/'3').
        Today's usable reconciliation source: every row carries a ``TransID``,
        a final ``Status`` and the ``Saldo Final`` after the sale.
        """
        return self._post(const.PATH_SALES, {'fecha': fecha, 'bolsa': bolsa})

    def get_deposit_reference(self):
        """The bank reference this account is funded through, and the URL of
        TAECEL's "report a deposit" form.

        Depositing against the reference credits the account automatically, so
        an affiliate never depends on its distributor transferring balance by
        hand (that path is portal-only and has a 30-minute confirmation window).

        Careful: unlike every other method, this one answers with a FLAT dict
        -- ``{"refCompra": ..., "urlReporte": ...}`` -- with no success/data
        envelope, so ``_post`` cannot tell success from failure and always
        reports ok=False. Verified live against a production account. We judge
        it here by whether a reference actually came back.
        """
        result = self._post(const.PATH_REPORT_URL)
        raw = result.raw if isinstance(result.raw, dict) else {}
        reference = str(raw.get(const.K_REPORT_REF) or '').strip()
        if not reference:
            return TaecelResult(
                False,
                message=result.message or _('The provider returned no deposit reference.'),
                raw=result.raw,
                timed_out=result.timed_out,
            )
        return TaecelResult(True, data={
            const.K_REPORT_REF: reference,
            const.K_REPORT_URL: str(raw.get(const.K_REPORT_URL) or '').strip(),
        }, raw=result.raw)

    def register_account(self, values):
        """Register an affiliate sub-account (the reseller-network model).

        ``values`` carries nombre, apellidos, correo, telefono, nomComercial,
        forzarActivacion, forzarCreacion, envioEmail. Returns the affiliate's
        own ws key/nip and payment references.
        """
        return self._post(const.PATH_REGISTER, dict(values or {}))

    # == Transactional endpoints (CONFIRMED) ==============================
    def request_txn(self, product_code, reference, amount=None, ref_cliente=None):
        """Dispatch a recharge/payment. Returns a result whose data carries the
        ``transID`` to hand to ``status_txn``.

        ``amount`` is sent only for free-amount (Tipo 1) carriers; TAECEL
        ignores it on fixed-price catalog products. ``ref_cliente`` is our own
        reference (refCte), echoed back in getSales.
        """
        payload = {
            const.PARAM_PRODUCT: product_code,
            const.PARAM_REFERENCE: reference,
        }
        if amount is not None:
            payload[const.PARAM_AMOUNT] = amount
        if ref_cliente:
            # TAECEL rejects a non-alphanumeric refCte with error 405, so strip
            # anything else (hyphens, spaces from a POS order reference...).
            clean = re.sub(r'[^A-Za-z0-9]', '', str(ref_cliente))
            if clean:
                payload[const.PARAM_REF_CLIENTE] = clean
        return self._post(const.PATH_REQUEST, payload)

    def status_txn(self, trans_id):
        """Query one transaction by transID. Idempotent: never dispatches, so it
        is safe to poll and to replay for reconciliation."""
        return self._post(const.PATH_STATUS, {const.PARAM_TRANS_ID: trans_id})

    def get_balance(self):
        """Read wallet balances directly (one row per bolsa)."""
        return self._post(const.PATH_BALANCE)
