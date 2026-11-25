/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { floatIsZero } from "@web/core/utils/numbers";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

/** «Force done» on an XPago transfer line asks XPago first: the sale is only marked paid when the money arrived. */
patch(PaymentScreen.prototype, {
    /** A transfer waits up to an hour for the money: the cashier may go on with other sales meanwhile. When the
     *  money arrives the sale of this line ends by itself: on the payment screen if it is on display, otherwise in
     *  the background (saved, receipt printed), without taking the register away from what the cashier is doing. */
    async sendPaymentRequest(line) {
        if (line.payment_method?.use_payment_terminal !== "xpago_spei") {
            return super.sendPaymentRequest(...arguments);
        }
        this.numberBuffer.capture();
        this.paymentLines.forEach((paymentLine) => (paymentLine.can_be_reversed = false));
        const order = line.order;
        // line.pay() by hand: a wait replaced by a newer one («Retry» after «Cancel») answers null and leaves the
        // line to the newer wait.
        line.set_payment_status("waiting");
        const paid = await line.payment_method.payment_terminal.send_payment_request(line.cid);
        if (paid === null) {
            return;
        }
        line.handle_payment_response(paid);
        if (
            !paid ||
            !order.is_paid() ||
            !floatIsZero(order.get_due(), this.pos.currency.decimal_places) ||
            !this.pos.config.auto_validate_terminal_payment
        ) {
            return;
        }
        // The same sale may come wrapped differently (reactive proxies): compare its id, not the object.
        const current = this.pos.get_order();
        if (current && current.uid === order.uid && this.pos.mainScreen.component === PaymentScreen) {
            this.validateOrder(false);
            return;
        }
        await this._xpagoValidateInBackground(order, line.amount);
    },

    /** The payment screen's own validation, on that sale instead of the one on display, and without changing the
     *  screen: the receipt is printed and the cashier stays where they are. */
    async _xpagoValidateInBackground(order, amount) {
        const money = this.env.utils.formatCurrency(amount);
        const sale = order.name || "";
        const screen = this;
        const background = Object.create(this, {
            currentOrder: { get: () => order },
            paymentLines: { get: () => order.get_paymentlines() },
            afterOrderValidation: {
                value: async () => {
                    const pos = screen.pos;
                    pos.db.remove_unpaid_order(order);
                    if (!order._printed && pos.config.iface_print_auto && (!order.is_to_invoice() || order.finalized)) {
                        await screen.printer.print(
                            OrderReceipt,
                            { data: order.export_for_printing(), formatCurrency: screen.env.utils.formatCurrency },
                            { webPrintFallback: true }
                        );
                    }
                    if (pos.get_order()?.uid !== order.uid) {
                        pos.removeOrder(order, false); // already saved: only out of the open sales
                    }
                },
            },
        });
        let ok = false;
        try {
            if (await background._isOrderValid(false)) {
                for (const payment of [...order.get_paymentlines()]) {
                    if (!payment.is_done()) {
                        order.remove_paymentline(payment);
                    }
                }
                const result = await background._finalizeValidation();
                ok = !(result instanceof Error) && order.finalized;
            }
        } catch {
            ok = false;
        }
        if (ok) {
            this.notification.add(
                _t("The transfer of %(amount)s arrived: sale %(sale)s was validated by itself.", {
                    amount: money,
                    sale,
                }),
                { type: "success" }
            );
            return;
        }
        // Something asks the cashier (a missing customer, an invoice…): the sale waits for them on the payment
        // screen, where the money already shows as received.
        this.notification.add(
            _t("The transfer of %(amount)s arrived, but sale %(sale)s could not be validated by itself.", {
                amount: money,
                sale,
            }),
            { type: "warning", sticky: true }
        );
    },

    async sendPaymentCancel(line) {
        if (line.payment_method?.use_payment_terminal !== "xpago_spei") {
            return super.sendPaymentCancel(...arguments);
        }
        line.set_payment_status("waitingCancel");
        const cancelled = await line.payment_method.payment_terminal.send_payment_cancel(line.order, line.cid);
        line.set_payment_status(cancelled ? "retry" : "waitingCard");
    },

    async sendForceDone(line) {
        const terminal = line.payment_method?.payment_terminal;
        if (line.payment_method?.use_payment_terminal !== "xpago_spei" || !terminal) {
            return super.sendForceDone(...arguments);
        }
        const tell = (body) => this.popup.add(ErrorPopup, { title: _t("XPago"), body });
        let view;
        try {
            view = await terminal._call("xpago_transfer_force_check", [
                { order_uuid: line.order.uid, amount: line.amount },
            ]);
        } catch {
            tell(_t("Could not ask XPago whether the transfer arrived. Check the connection and try again."));
            return;
        }
        if (view.state !== "paid") {
            tell(
                ["awaiting", "expired"].includes(view.state)
                    ? _t("The transfer has not arrived yet. Wait for it, or press Cancel.")
                    : _t("XPago has no transfer of this amount for this sale. It is not marked as paid.")
            );
            return;
        }
        const entry = terminal.transfers[line.cid];
        if (entry) {
            // The register is still waiting: its next look sees the money and completes the line.
            Object.assign(entry.view, view);
            return;
        }
        Object.assign(line, view.payment);
        line.set_payment_status("done");
        const order = line.order;
        if (
            order.is_paid() &&
            floatIsZero(order.get_due(), this.pos.currency.decimal_places) &&
            this.pos.config.auto_validate_terminal_payment
        ) {
            this.validateOrder(false);
        }
    },
});
