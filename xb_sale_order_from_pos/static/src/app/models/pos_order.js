/** @odoo-module **/
// XUBAX - Sales, Quotations & Layaway from POS (Phase 3 - display only)
// Exposes the linked Sale Order totals to the receipt. Clean-room, native-only.
// Odoo 17: the receipt is drawn from Order.export_for_printing(), so everything the
// receipt shows is added to that data here.

import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models";
import { qrCodeSrc } from "@point_of_sale/utils";
import { deserializeDateTime, formatDate } from "@web/core/l10n/dates";
import { roundPrecision as round_pr } from "@web/core/utils/numbers";

const { DateTime } = luxon;

patch(Order.prototype, {
    // The Sale Order created from this cart (set by xbCreateOrderFromPos), kept with the
    // order so a reload does not lose it.
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.xbSaleOrder = json.xb_sale_order || null;
    },
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        if (this.xbSaleOrder) {
            json.xb_sale_order = this.xbSaleOrder;
        }
        return json;
    },

    /**
     * Return { name, total, paid, balance, portalUrl, ... } for the Sale Order this POS
     * order relates to, or null when there is none.
     * - Primary source: the stash written by xbCreateOrderFromPos when the SO was
     *   created from this cart (carries the portal URL too).
     * - Fallback: the SO a line points to (sale_order_origin_id, read by pos_sale when
     *   the order is recovered). Its amount_unpaid is FRESH after a payment:
     *   pos.order.create_from_ui sends the recomputed SO back and the store copies it
     *   onto this object before the receipt is drawn.
     * paid = total - balance (balance is sale.order.amount_unpaid, clamped >= 0).
     */
    xbGetSaleOrderTotals() {
        const stash = this.xbSaleOrder;
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
                deliveryDate: stash.commitment_date ? DateTime.fromISO(stash.commitment_date) : null,
                layawayDeadline: stash.layaway_deadline
                    ? DateTime.fromISO(stash.layaway_deadline)
                    : null,
            };
        } else {
            const so = this.get_orderlines().find((l) => l.sale_order_origin_id)
                ?.sale_order_origin_id;
            if (so) {
                const baseUrl = this.pos.base_url || "";
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
                            : null,
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
    // commitment_date of a loaded SO: the server's UTC string.
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
    // (h) Component breakdown for the advance ticket: the recovered Sale Order's own
    // PRODUCT lines (name, qty, total), read when it was recovered.
    xbSaleDetails() {
        const so = this.get_orderlines().find((l) => l.sale_order_origin_id)?.sale_order_origin_id;
        const lines = so?.xb_lines || [];
        return lines.length ? lines : null;
    },
    // (PRIORITY) Cash-rounding display that always balances: computed from the TOTAL
    // itself (independent of what was tendered), whenever cash rounding applies to this
    // order. Total + Rounding = To Pay.
    xbRounding() {
        const config = this.pos.config;
        const cashRounding = this.pos.cash_rounding?.[0];
        if (!config.cash_rounding || !cashRounding) {
            return null;
        }
        if (
            config.only_round_cash_method &&
            !this.get_paymentlines().some((p) => p.payment_method.is_cash_count)
        ) {
            return null;
        }
        const total = this.get_total_with_tax();
        const step = cashRounding.rounding;
        let rounded;
        if (cashRounding.rounding_method === "UP") {
            rounded = Math.ceil(round_pr(total / step, 1e-9)) * step;
        } else if (cashRounding.rounding_method === "DOWN") {
            rounded = Math.floor(round_pr(total / step, 1e-9)) * step;
        } else {
            rounded = round_pr(total, step);
        }
        rounded = round_pr(rounded, this.pos.currency.rounding);
        const amount = round_pr(rounded - total, this.pos.currency.rounding);
        return amount ? { amount, toPay: rounded } : null;
    },
    export_for_printing() {
        const data = super.export_for_printing(...arguments);
        const config = this.pos.config;
        const so = this.xbGetSaleOrderTotals();
        data.xbSaleOrder = so;
        data.xbEnrich = Boolean(config.xb_enrich_receipt && so);
        data.xbSaleDetails = so ? this.xbSaleDetails() : null;
        // (c) Payment QR: only while there is still a balance to pay.
        data.xbPortalQr =
            data.xbEnrich && config.xb_show_portal_link && so.portalUrl && so.balance > 0
                ? qrCodeSrc(so.portalUrl, { size: 160 })
                : false;
        data.xbRounding = this.xbRounding();
        // Self-invoice QR only when settled (xb_autofactura_qr_paid_only): hide the
        // native self-invoice QR/code while a Sale Order balance is pending.
        if (config.xb_autofactura_qr_paid_only && so && so.balance > 0) {
            data.pos_qr_code = false;
            data.ticket_code = false;
        }
        data.headerData = {
            ...data.headerData,
            xbSaleOrder: so,
            xbPartnerName: so ? this.get_partner()?.name || "" : "",
        };
        return data;
    },
});
