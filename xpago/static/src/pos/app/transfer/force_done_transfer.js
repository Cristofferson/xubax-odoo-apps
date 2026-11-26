import { _t } from "@web/core/l10n/translation";
import { onWillUnmount } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

/** «Force done» on an XPago transfer line asks XPago first: the sale is only marked paid when the money arrived. */
patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        // «Finish the sale» of a transfer that arrived meanwhile validates on the payment screen it opens.
        this.pos.xpagoPaymentScreen = this;
        onWillUnmount(() => {
            if (this.pos.xpagoPaymentScreen === this) {
                this.pos.xpagoPaymentScreen = null;
            }
        });
    },

    /** A transfer waits up to an hour for the money, with no terminal busy: it must not hold the register's
     *  «electronic payment in progress» lock, or the card cannot be used in the other sales meanwhile. */
    async sendPaymentRequest(line) {
        if (line.payment_method_id?.use_payment_terminal !== "xpago_spei") {
            return super.sendPaymentRequest(...arguments);
        }
        this.numberBuffer.capture();
        this.paymentLines.forEach((paymentLine) => (paymentLine.can_be_reversed = false));
        const order = line.pos_order_id;
        // line.pay() by hand: a wait replaced by a newer one («Retry» after «Cancel») answers null and leaves the
        // line to the newer wait.
        line.setPaymentStatus("waiting");
        const paid = await line.payment_method_id.payment_terminal.sendPaymentRequest(line.uuid);
        if (paid === null) {
            return;
        }
        line.handlePaymentResponse(paid);
        if (!paid || !order.isPaid() || !this.pos.config.auto_validate_terminal_payment || order.isRefundInProcess()) {
            return;
        }
        if (this._xpagoOnScreen(order)) {
            // The cashier may have left and come back: the payment screen on display validates.
            (this.pos.xpagoPaymentScreen || this).validateOrder(false);
            return;
        }
        // The money arrived while the cashier was on another sale or screen: the sale ends by itself in the
        // background (saved, receipt printed), without taking the register away from what the cashier is doing.
        await this._xpagoValidateInBackground(order, line.amount);
    },

    /** The payment screen's own validation, on that sale instead of the one on display, and without changing the
     *  screen: the receipt is printed and the cashier stays where they are. (saas~18.3 has no OrderPaymentValidation:
     *  the payment screen's steps run on a copy of it that points to that sale.) */
    async _xpagoValidateInBackground(order, amount) {
        const money = this.env.utils.formatCurrency(amount);
        const sale = order.pos_reference || order.name || "";
        const screen = this;
        const background = Object.create(this, {
            currentOrder: { get: () => order },
            paymentLines: { get: () => order.payment_ids },
            afterOrderValidation: {
                value: async () => {
                    const pos = screen.pos;
                    if (order.nb_print === 0 && pos.config.iface_print_auto && (!order.isToInvoice() || order.finalized)) {
                        pos.printReceipt({ order });
                    }
                },
            },
        });
        let ok = false;
        try {
            if (await background._isOrderValid(false)) {
                for (const payment of [...order.payment_ids]) {
                    if (!payment.isDone() || payment.amount === 0) {
                        order.removePaymentline(payment);
                    }
                }
                const result = await background._finalizeValidation();
                ok = result !== false && !(result instanceof Error) && order.state === "paid";
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
        // Something asks the cashier (a missing customer, an invoice…): the sale waits for them, one tap away.
        const close = this.notification.add(
            _t("The transfer of %(amount)s arrived, but sale %(sale)s could not be validated by itself.", {
                amount: money,
                sale,
            }),
            {
                type: "warning",
                sticky: true,
                buttons: [
                    {
                        name: _t("Open the sale"),
                        primary: true,
                        onClick: () => {
                            close();
                            this.pos.setOrder(order);
                            this.pos.showScreen("PaymentScreen");
                        },
                    },
                ],
            }
        );
    },

    _xpagoOnScreen(order) {
        const current = this.pos.getOrder();
        return (
            (current === order || current?.uuid === order.uuid) &&
            this.pos.mainScreen?.component?.name === "PaymentScreen"
        );
    },

    async sendPaymentCancel(line) {
        if (line.payment_method_id?.use_payment_terminal !== "xpago_spei") {
            return super.sendPaymentCancel(...arguments);
        }
        line.setPaymentStatus("waitingCancel");
        const cancelled = await line.payment_method_id.payment_terminal.sendPaymentCancel(line.pos_order_id, line.uuid);
        line.setPaymentStatus(cancelled ? "retry" : "waitingCard");
    },

    async sendForceDone(line) {
        const terminal = line.payment_method_id?.payment_terminal;
        if (line.payment_method_id?.use_payment_terminal !== "xpago_spei" || !terminal) {
            return super.sendForceDone(...arguments);
        }
        const tell = (body) => this.dialog.add(AlertDialog, { title: _t("XPago"), body });
        let view;
        try {
            view = await terminal._call("xpago_transfer_force_check", [
                { order_uuid: line.pos_order_id.uuid, amount: line.amount },
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
        const entry = terminal.transfers[line.uuid];
        if (entry) {
            // The register is still waiting: its next look sees the money and completes the line.
            Object.assign(entry.view, view);
            return;
        }
        Object.assign(line, view.payment);
        line.setPaymentStatus("done");
        const order = line.pos_order_id;
        if (order.isPaid() && this.pos.config.auto_validate_terminal_payment && !order.isRefundInProcess()) {
            this.validateOrder(false);
        }
    },
});
