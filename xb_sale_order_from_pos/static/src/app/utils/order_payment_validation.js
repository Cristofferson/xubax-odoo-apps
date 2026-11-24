/** @odoo-module **/
// XUBAX - Sales, Quotations & Layaway from POS (Phase 4)
// Payment-validation guards for our POS-originated sale orders. Clean-room,
// native-only: reuses the native down-payment / settle flow and only adds guards.

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { roundPrecision as round_pr } from "@web/core/utils/numbers";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

patch(PaymentScreen.prototype, {
    async _isOrderValid(isForceValidate) {
        const order = this.currentOrder;
        // Guard 1 — a LAYAWAY must collect SOME advance to be confirmed: block when a
        // down-payment line links to a layaway SO but nothing is being collected.
        // Order = optional advance (0 allowed); Quotation = full.
        const layawayLine = order
            .get_orderlines()
            .find((l) => l.sale_order_origin_id?.xb_so_kind === "layaway");
        if (layawayLine && order.get_total_with_tax() <= 0) {
            this.popup.add(ErrorPopup, {
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
            this.popup.add(ErrorPopup, {
                title: _t("Layaway terms"),
                body: layawayError,
            });
            return false;
        }

        // Guard 2 — when SETTLING one of our SOs (the order carries its product
        // lines, not just an advance), the amount being collected for that SO must
        // equal its real balance (sale.order.amount_unpaid) to the cent.
        const dpId = this.pos.config.down_payment_product_id?.[0];
        if (dpId) {
            for (const [so, lines] of this.xbLinesBySo(["quotation", "order", "layaway", "order_layaway"])) {
                const isSettle = lines.some((l) => l.get_product().id !== dpId);
                if (!isSettle) {
                    continue; // pure (partial) down payment, not a settle
                }
                const portion = lines.reduce((s, l) => s + (l.get_price_with_tax() || 0), 0);
                // Round with the currency before comparing: the float sum can land
                // 5e-15 above the 1-cent tolerance.
                const delta = Math.abs(this.xbRound(portion - so.amount_unpaid));
                if (delta > 0.01) {
                    this.popup.add(ErrorPopup, {
                        title: _t("Balance mismatch"),
                        body: _t(
                            "The amount to settle for %s (%s) does not match its balance (%s). Reload the order and try again.",
                            so.name,
                            this.env.utils.formatCurrency(portion),
                            this.env.utils.formatCurrency(so.amount_unpaid)
                        ),
                    });
                    return false;
                }
            }
        }

        return super._isOrderValid(...arguments);
    },

    xbRound(value) {
        return round_pr(value, this.pos.currency.rounding);
    },

    // Lines of the current order grouped by the Sale Order (of the given kinds) they
    // belong to. The SO is matched by id: after a reload each line holds its own copy.
    xbLinesBySo(kinds) {
        const bySo = new Map();
        const soById = new Map();
        for (const l of this.currentOrder.get_orderlines()) {
            const so = l.sale_order_origin_id;
            if (!so || !kinds.includes(so.xb_so_kind)) {
                continue;
            }
            const key = soById.get(so.id) || soById.set(so.id, so).get(so.id);
            (bySo.get(key) || bySo.set(key, []).get(key)).push(l);
        }
        return bySo;
    },

    xbLayawayPaymentError() {
        const dpId = this.pos.config.down_payment_product_id?.[0];
        const fmt = (v) => this.env.utils.formatCurrency(v);
        const round = (v) => this.xbRound(v);
        for (const [so, lines] of this.xbLinesBySo(["layaway", "order", "order_layaway"])) {
            if (lines.some((l) => l.get_product().id !== dpId)) {
                continue; // a settle: Guard 2 checks it equals the balance
            }
            const amount = round(lines.reduce((s, l) => s + (l.get_price_with_tax() || 0), 0));
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
