# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS
# Original, clean-room implementation. Native-only logic.
import logging

from odoo import Command, api, fields, models
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def sync_from_ui(self, *args, **kwargs):
        # Round-trip (Bug A/B + receipt title): inject the FRESH linked Sale Orders
        # (amount_unpaid + state, recomputed by super() as the down payment / settle was
        # applied) into the sync response. The frontend (pos_store.syncAllOrders ->
        # data.missingRecursive -> models.loadConnectedData) updates the EXISTING SO
        # models by id, so the receipt reads the post-payment amount_unpaid DIRECTLY on
        # the initial print, not only after a reload — which lets the getter use
        # so.amount_unpaid as-is (no `amount_unpaid - priceIncl` projection, which
        # over-counted loose products and double-subtracted on reprint). Scoped to orders
        # that link a SO -> normal POS sales inject nothing. Keeps the native signature/
        # decorator and forwards *args/**kwargs verbatim. Best-effort: never break sync.
        data = super().sync_from_ui(*args, **kwargs)
        try:
            synced = self.browse([r["id"] for r in (data.get("pos.order") or []) if r.get("id")])
            linked_sos = synced.lines.sale_order_origin_id
            config = synced.config_id[:1]
            if linked_sos and config:
                so_fields = linked_sos._load_pos_data_fields(config)
                data.setdefault("sale.order", [])
                seen = {r.get("id") for r in data["sale.order"]}
                data["sale.order"].extend(
                    rec for rec in linked_sos.read(so_fields, load=False) if rec["id"] not in seen
                )
        except Exception as ex:  # noqa: BLE001
            _logger.warning("xb sale.order round-trip error: %s", ex)
        return data

    def _xb_has_our_so(self):
        """True if any of these orders is linked to one of our SOs (xb_so_kind set)."""
        return any(
            line.sale_order_origin_id.xb_so_kind
            for line in self.lines
            if line.sale_order_origin_id
        )

    def _xb_is_mx(self):
        """True when the order's company files taxes in Mexico, i.e. the Mexican
        localization is actually in effect. Keyed on the FISCAL country
        (account_fiscal_country_id) exactly like l10n_mx_edi resolves a move's
        country_code -- NOT on res.company.country_id, which can be MX while the
        company still runs a generic chart. Every CFDI/SAT touchpoint below is gated
        on this, so on a non-Mexican company they stay dormant and the invoice keeps
        pure native behaviour. The SAT forma de pago lives in the
        xb_sale_order_from_pos_l10n_mx bridge (installed with l10n_mx_edi)."""
        company = self.company_id[:1]
        return (company.account_fiscal_country_id.code or company.country_id.code) == "MX"

    def _prepare_account_move_line_data_for_rounding(self, invoice):
        # Exact CFDI for our flow (continuation of the invoice_cash_rounding_id drop
        # in _prepare_invoice_vals). When config cash rounding is on, Odoo adds a
        # rounding line to make the invoice equal the cash TENDERED (which differs from
        # the exact amount by the change rounding). We keep the CFDI at the exact
        # amount; the cash-tendering difference is a POS cash matter, not a fiscal one.
        # Odoo's own removal of the move-level rounding line is kept; only the added
        # tendering rounding line is left out. Ordinary POS invoices are untouched.
        # MX-only: outside Mexico (_xb_is_mx() False) the invoice keeps the native
        # cash-rounding behaviour.
        commands = super()._prepare_account_move_line_data_for_rounding(invoice)
        if not (self._xb_has_our_so() and self.config_id[:1].cash_rounding and self._xb_is_mx()):
            return commands
        return [
            command for command in commands
            if not (command[0] == Command.CREATE and command[2].get("display_type") == "rounding")
        ]

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        # Branch fix: attribute the POS invoice to the ORDER's company (e.g. the
        # Anello branch), not the shared invoice journal's company (the principal).
        # The native vals omit company_id, so account.move._compute_company_id
        # defaults it to journal.company_id._accessible_branches()[:1] -> the root
        # company. The branch then loses its identity: the move (and its CFDI/RFC)
        # is issued under the principal, and the branch income account does not
        # resolve ("Falta la cuenta requerida"). Set it explicitly so the move keeps
        # the order's company (the journal's company is a parent, so it is kept).
        vals["company_id"] = self.company_id.id
        # Exact CFDI for our flow: drop the POS cash rounding from the invoice.
        # Cash rounding (e.g. "10 Centavos", add_invoice_line) exists to give change
        # on cash payments; it must NOT alter the fiscal document, which has to mirror
        # the exact amount. Left in, account.move's cash-rounding recomputation adds a
        # +-rounding line to the move total, distorting the CFDI and stacking on top of
        # our 1-cent settle reconciliation (Option 1/2). Scoped to our orders only;
        # ordinary POS invoices keep the native behaviour.
        #
        # MX-only: on a non-Mexican company the invoice keeps the native cash rounding.
        # The SAT forma de pago is added by xb_sale_order_from_pos_l10n_mx.
        if self._xb_has_our_so() and self._xb_is_mx():
            vals["invoice_cash_rounding_id"] = False
        return vals

    # ------------------------------------------------------------------
    # Receipt (Odoo 20 draws it from QWeb, also on the server: download, email)
    # ------------------------------------------------------------------
    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt)
        data["extra_data"].update(self._xb_receipt_sale_order_data())
        return data

    def _xb_receipt_sale_order_data(self):
        """Same values as the register's GeneratePrinterData.xbGenerateSaleOrderData, for an
        order saved on the server: its Sale Order is the one its lines settle or pay."""
        self.ensure_one()
        result = {"xb_so": False, "xb_created": False, "xb_hide_self_invoice_qr": False}
        so = self.lines.sale_order_origin_id[:1].sudo()
        if not so:
            return result
        config = self.config_id
        balance = max(so.amount_unpaid, 0.0)
        paid = so.amount_total - balance
        kind = so.xb_so_kind or False
        if kind == "quotation" and so.state == "sale":
            kind = "order"
        tz = self._order_receipt_tz()
        delivery_date = False
        if so.commitment_date:
            delivery_date = format_date(
                self.env, fields.Datetime.context_timestamp(self.with_context(tz=tz), so.commitment_date).date())
        enrich = config.xb_enrich_receipt
        details = []
        if enrich and balance > 0:
            details = [{
                "qty": int(line.product_uom_qty) if float(line.product_uom_qty).is_integer() else line.product_uom_qty,
                "name": line.product_id.display_name or line.name,
                "total": self._order_receipt_format_currency(line.price_total),
            } for line in so.order_line if not line.is_downpayment and line.product_id]
        portal_qr = False
        if enrich and config.xb_show_portal_link and balance > 0:
            portal_qr = self._order_receipt_generate_qr_code(so.get_base_url() + so.get_portal_url())
        result["xb_so"] = {
            "kind": kind,
            "name": so.name,
            "partner_ref": self.partner_id.ref or False,
            "delivery_date": delivery_date,
            "layaway_deadline": format_date(self.env, so.xb_layaway_deadline)
            if so.xb_layaway_deadline and balance > 0 else False,
            "show_summary": bool(enrich and paid > 0),
            "settled": balance <= 0,
            "total": self._order_receipt_format_currency(so.amount_total),
            "paid": self._order_receipt_format_currency(paid),
            "balance": self._order_receipt_format_currency(balance),
            "details": details,
            "portal_qr": portal_qr,
        }
        result["xb_hide_self_invoice_qr"] = bool(config.xb_autofactura_qr_paid_only and balance > 0)
        return result
