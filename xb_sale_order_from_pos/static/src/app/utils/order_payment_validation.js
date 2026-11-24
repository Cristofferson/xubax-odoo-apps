// XUBAX - Sales, Quotations & Layaway from POS (Phase 4)
// Payment-validation guards for our POS-originated sale orders. Clean-room,
// native-only: reuses the native down-payment / settle flow and only adds guards.

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";

patch(OrderPaymentValidation.prototype, {
    async askBeforeValidation() {
        // Guard 1 — a LAYAWAY must collect SOME advance to be confirmed: block when a
        // down-payment line links to a layaway SO but nothing is being collected
        // (priceIncl <= 0). Order = optional advance (0 allowed); Quotation = full.
        const layawayLine = this.order
            .getOrderlines()
            .find((l) => l.sale_order_origin_id?.xb_so_kind === "layaway");
        if (layawayLine && this.order.priceIncl <= 0) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Advance required"),
                body: _t("This layaway requires an advance."),
            });
            return false;
        }

        // Guard 1b (1.3.0) — layaway terms on a payment (down payment line only, a
        // settle is checked by Guard 2): an expired layaway takes no payment, the
        // first payment reaches the minimum down payment and the next ones the
        // minimum payment, unless the payment settles the whole balance.
        const layawayError = this.xbLayawayPaymentError();
        if (layawayError) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Layaway terms"),
                body: layawayError,
            });
            return false;
        }

        // Guard 2 — when SETTLING one of our SOs (the order carries its product
        // lines, not just an advance), the amount being collected for that SO must
        // equal its real balance (sale.order.amount_unpaid, the source of truth from
        // actual payments) to the cent. Defense for the multi-advance settle edge
        // cases (an advance still uninvoiced, a re-settle, ...). Scoped to each SO's
        // own portion = sum of its lines' priceIncl (credits are negative).
        const dpId = this.pos.config.raw?.down_payment_product_id;
        if (dpId) {
            const bySo = new Map();
            for (const l of this.order.getOrderlines()) {
                const so = l.sale_order_origin_id;
                if (!so?.xb_so_kind) {
                    continue;
                }
                (bySo.get(so) || bySo.set(so, []).get(so)).push(l);
            }
            for (const [so, lines] of bySo) {
                const isSettle = lines.some((l) => l.product_id.id !== dpId);
                if (!isSettle) {
                    continue; // pure (partial) down payment, not a settle
                }
                const portion = lines.reduce((s, l) => s + (l.priceIncl || 0), 0);
                // Round with the currency before comparing: the float sum can land
                // 5e-15 above the 1-cent tolerance (120.00 - 65.01 = 54.989999...)
                // and block the exactly-1-cent case the tolerance exists for.
                const delta = Math.abs(this.pos.currency.round(portion - so.amount_unpaid));
                if (delta > 0.01) {
                    this.pos.dialog.add(AlertDialog, {
                        title: _t("Balance mismatch"),
                        body: _t(
                            "The amount to settle for %s (%s) does not match its balance (%s). Reload the order and try again.",
                            so.name,
                            this.pos.formatCurrency(portion),
                            this.pos.formatCurrency(so.amount_unpaid)
                        ),
                    });
                    return false;
                }
            }
        }

        return super.askBeforeValidation();
    },

    xbLayawayPaymentError() {
        const dpId = this.pos.config.raw?.down_payment_product_id;
        const fmt = (v) => this.pos.formatCurrency(v);
        const round = (v) => this.pos.currency.round(v);
        const bySo = new Map();
        for (const l of this.order.getOrderlines()) {
            const so = l.sale_order_origin_id;
            if (!["layaway", "order", "order_layaway"].includes(so?.xb_so_kind)) {
                continue;
            }
            (bySo.get(so) || bySo.set(so, []).get(so)).push(l);
        }
        for (const [so, lines] of bySo) {
            if (lines.some((l) => l.product_id.id !== dpId)) {
                continue; // a settle: Guard 2 checks it equals the balance
            }
            const amount = round(lines.reduce((s, l) => s + (l.priceIncl || 0), 0));
            if (amount <= 0) {
                continue; // a refund of a down payment is not a payment
            }
            if (so.xb_so_kind !== "layaway") {
                // An order: only its first payment has a minimum (the down payment).
                const balanceO = round(so.amount_unpaid || 0);
                const paidO = round((so.amount_total || 0) - balanceO);
                const minO = round(((so.amount_total || 0) * (so.xb_layaway_down_percent || 0)) / 100);
                if (paidO <= 0 && amount < balanceO && amount < minO) {
                    return _t(
                        "The down payment of %(name)s is at least %(minimum)s (%(percent)s% of the price).",
                        { name: so.name, minimum: fmt(minO), percent: so.xb_layaway_down_percent }
                    );
                }
                continue;
            }
            if (so.xb_layaway_state === "expired") {
                return _t(
                    "Layaway %s expired. Extend its deadline from Sales before taking more payments.",
                    so.name
                );
            }
            const balance = round(so.amount_unpaid || 0);
            if (amount >= balance) {
                continue;
            }
            const paid = round((so.amount_total || 0) - balance);
            if (paid <= 0) {
                const minimum = round(((so.amount_total || 0) * (so.xb_layaway_down_percent || 0)) / 100);
                if (amount < minimum) {
                    return _t(
                        "The down payment of %(name)s is at least %(minimum)s (%(percent)s% of the price).",
                        { name: so.name, minimum: fmt(minimum), percent: so.xb_layaway_down_percent }
                    );
                }
            } else if (so.xb_layaway_min_payment && amount < round(so.xb_layaway_min_payment)) {
                return _t(
                    "The minimum payment on %(name)s is %(minimum)s, unless it pays the whole balance (%(balance)s).",
                    { name: so.name, minimum: fmt(so.xb_layaway_min_payment), balance: fmt(balance) }
                );
            }
        }
        return false;
    },
});
