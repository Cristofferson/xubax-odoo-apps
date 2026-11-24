/** @odoo-module **/
// XUBAX - Sales, Quotations & Layaway from POS (Phase 3 - display only)
// Exposes the linked Sale Order totals to the receipt. Clean-room, native-only.

import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { deserializeDateTime, formatDate } from "@web/core/l10n/dates";
import { qrCodeSrc } from "@point_of_sale/utils";
import { roundCurrency } from "@point_of_sale/app/models/utils/currency";

const { DateTime } = luxon;

patch(PosOrder.prototype, {
    /**
     * Return { name, total, paid, balance, portalUrl } for the Sale Order this POS
     * order relates to, or null when there is none.
     * - Primary source: the uiState stash written by xbCreateOrderFromPos when the
     *   SO was created from this cart (carries the portal URL too).
     * - Fallback: the SO natively linked to a line via sale_order_origin_id, whose
     *   amount_total / amount_unpaid are loaded client-side by pos_sale. The portal
     *   URL is not loaded in this path, so portalUrl is null there.
     * paid = total - balance (balance is sale.order.amount_unpaid, clamped >= 0).
     */
    xbGetSaleOrderTotals() {
        const stash = this.uiState?.xbSaleOrder;
        let data = null;
        if (stash) {
            data = {
                name: stash.name,
                total: stash.amount_total,
                balance: stash.amount_unpaid,
                portalUrl: stash.portal_url || null,
                type: stash.type || null,
                state: stash.state || null,
                partnerRef: stash.partner_ref || null,
                // A day already ("YYYY-MM-DD"), in the shop's time zone.
                deliveryDate: stash.commitment_date
                    ? DateTime.fromISO(stash.commitment_date)
                    : null,
                layawayDeadline: stash.layaway_deadline
                    ? DateTime.fromISO(stash.layaway_deadline)
                    : null,
            };
        } else {
            const so = this.lines?.find((l) => l.sale_order_origin_id)
                ?.sale_order_origin_id;
            if (so) {
                // so.amount_unpaid is FRESH (post-payment): pos.order.sync_from_ui
                // injects the recomputed linked SO into the sync response, so the SO
                // model is updated before the receipt renders. Use it directly — no
                // projection. The old `amount_unpaid - priceIncl` over-subtracted loose
                // products sold in the same ticket (Bug A) and double-subtracted on
                // reprint once amount_unpaid was fresh (Bug B). The backend balance is
                // the source of truth.
                // Build the SO portal URL from its access_token (the stash's
                // portal_url is only present on creation). Use config._base_url, the
                // same base the native ticket QR uses (session._base_url in Odoo 18), for the payment QR on
                // recovered SOs.
                const baseUrl = this.session?._base_url || "";
                const portalUrl = so.access_token
                    ? `${baseUrl}/my/orders/${so.id}?access_token=${so.access_token}`
                    : null;
                data = {
                    name: so.name,
                    total: so.amount_total,
                    balance: Math.max(so.amount_unpaid || 0, 0),
                    portalUrl,
                    type: so.xb_so_kind || null,
                    state: so.state || null,
                    partnerRef: null,
                    deliveryDate: this.xbAsDateTime(so.commitment_date),
                    layawayDeadline:
                        typeof so.xb_layaway_deadline === "string"
                            ? DateTime.fromISO(so.xb_layaway_deadline)
                            : so.xb_layaway_deadline || null,
                };
            }
        }
        if (!data) {
            return null;
        }
        // Fallback for the customer reference: the loaded partner, if it carries one.
        if (!data.partnerRef) {
            data.partnerRef = this.get_partner()?.ref || null;
        }
        const deliveryDate =
            data.deliveryDate && data.deliveryDate.isValid ? formatDate(data.deliveryDate) : null;
        const layawayDeadline =
            data.layawayDeadline && data.layawayDeadline.isValid && data.balance > 0
                ? formatDate(data.layawayDeadline)
                : null;
        return { ...data, deliveryDate, layawayDeadline, paid: data.total - data.balance };
    },
    // commitment_date of a loaded SO: a luxon DateTime, or the server's UTC string.
    xbAsDateTime(value) {
        if (!value) {
            return null;
        }
        if (typeof value === "string") {
            try {
                return deserializeDateTime(value);
            } catch {
                return null;
            }
        }
        return value;
    },

    // ------------------------------------------------------------------
    // Receipt (Odoo 18): the receipt renders from export_for_printing() data, so the
    // Sale Order block, the type header and the rounding fix travel in that data.
    // ------------------------------------------------------------------
    export_for_printing(baseUrl, headerData) {
        const result = super.export_for_printing(...arguments);
        let so = null;
        try {
            so = this.xbGetSaleOrderTotals();
        } catch (error) {
            // Never take the receipt down for our extra block.
            console.warn("[xb] sale order totals unavailable on the receipt:", error);
        }
        const config = this.config;
        result.xbSaleOrder = so;
        result.xbEnrich = Boolean(config?.xb_enrich_receipt && so);
        result.xbSaleDetails = so ? this.xbSaleDetails() : null;
        result.xbPortalQr =
            so && config?.xb_show_portal_link && so.portalUrl && so.balance > 0
                ? this.xbPortalQrCode(so.portalUrl)
                : null;
        // Self-invoice ("Need an invoice?") QR gating, per POS
        // (xb_autofactura_qr_paid_only): hidden while a Sale Order balance is pending.
        if (config?.xb_autofactura_qr_paid_only && so && so.balance > 0) {
            result.pos_qr_code = false;
        }
        // Cash rounding that always balances: computed from the TOTAL itself, so it
        // shows with or without change (Total + Rounding = To Pay).
        const rounded = this.xbRoundedTotal();
        const roundingAmount =
            rounded === null
                ? 0
                : roundCurrency(rounded - this.get_total_with_tax(), this.currency);
        result.xbRounding = {
            show: rounded !== null && roundingAmount !== 0,
            amount: roundingAmount,
            total: rounded,
        };
        if (so && so.type) {
            const kind = so.type === "quotation" && so.state === "sale" ? "order" : so.type;
            result.headerData = {
                ...result.headerData,
                xbSo: {
                    kind,
                    name: so.name,
                    deliveryDate: so.deliveryDate,
                    layawayDeadline: so.layawayDeadline,
                    partnerRef: so.partnerRef,
                    partnerName: this.get_partner()?.name || "",
                },
            };
        }
        return result;
    },
    // The recovered Sale Order's own PRODUCT lines (name, qty, total), shown on the
    // advance ticket. Down-payment and non-product lines are left out.
    xbSaleDetails() {
        const so = this.lines?.find((l) => l.sale_order_origin_id)?.sale_order_origin_id;
        const lines = (so?.order_line || []).filter((l) => !l.is_downpayment && l.product_id);
        return lines.length
            ? lines.map((l) => ({
                  product_uom_qty: l.product_uom_qty,
                  product_name: l.product_id.display_name || l.display_name || "",
                  total: l.price_total,
              }))
            : null;
    },
    xbRoundedTotal() {
        const config = this.config;
        const applies =
            config?.cash_rounding &&
            config.rounding_method &&
            (!config.only_round_cash_method || this.is_paid_with_cash());
        return applies
            ? this.getRoundedRemaining(config.rounding_method, this.get_total_with_tax())
            : null;
    },
    // The SO online portal link as a QR. A QR failure must never break the receipt.
    xbPortalQrCode(url) {
        if (!url) {
            return null;
        }
        try {
            return qrCodeSrc(url);
        } catch (e) {
            console.warn("[xb] payment QR generation failed:", e, url);
            return null;
        }
    },
});
