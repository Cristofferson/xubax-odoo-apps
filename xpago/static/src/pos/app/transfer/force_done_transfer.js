/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { floatIsZero } from "@web/core/utils/numbers";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

/** «Force done» on an XPago transfer line asks XPago first: the sale is only marked paid when the money arrived. */
patch(PaymentScreen.prototype, {
    /** A transfer waits up to an hour for the money: the cashier may go on with other sales meanwhile, so only the
     *  sale of this line is validated when the money arrives, and only while it is still on the payment screen. */
    async sendPaymentRequest(line) {
        if (line.payment_method?.use_payment_terminal !== "xpago_spei") {
            return super.sendPaymentRequest(...arguments);
        }
        this.numberBuffer.capture();
        this.paymentLines.forEach((paymentLine) => (paymentLine.can_be_reversed = false));
        const order = line.order;
        const paid = await line.pay();
        if (
            paid &&
            order.is_paid() &&
            floatIsZero(order.get_due(), this.pos.currency.decimal_places) &&
            this.pos.config.auto_validate_terminal_payment &&
            this.pos.get_order() === order &&
            this.pos.mainScreen.component === PaymentScreen
        ) {
            this.validateOrder(false);
        }
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
