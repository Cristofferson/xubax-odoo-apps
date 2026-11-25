import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PosPaymentMethod } from "@point_of_sale/app/models/pos_payment_method";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";

/** A transfer waits up to an hour for the money, with no terminal busy: it must not count as an «electronic payment
 *  in progress», or the card terminal cannot be used in the other sales meanwhile. */
patch(PosPaymentMethod.prototype, {
    _checkOrder({ order, paymentline }) {
        if (this.payment_provider === "xpago_spei") {
            return { status: true, message: "" };
        }
        const busy = order.payment_ids.some(
            (pl) =>
                pl.uuid !== paymentline?.uuid &&
                pl.payment_method_id.payment_provider !== "xpago_spei" &&
                this.payment_method_type === pl.payment_method_id.payment_method_type &&
                pl.isProcessing()
        );
        if (busy) {
            return { status: false, message: _t("There is already an electronic payment in progress.") };
        }
        return { status: true, message: "" };
    },
});

/** «Force done» on an XPago transfer line asks XPago first: the sale is only marked paid when the money arrived. */
patch(PaymentScreen.prototype, {
    /** The money may arrive long after, while the cashier is on another sale: that sale ends by itself. */
    async sendPaymentRequest(line) {
        if (line.payment_method_id?.payment_provider !== "xpago_spei") {
            return super.sendPaymentRequest(...arguments);
        }
        this.numberBuffer.capture();
        const order = line.pos_order_id;
        // line.pay() by hand: a wait replaced by a newer one («Retry» after «Cancel») answers null and leaves the
        // line to the newer wait.
        line.setPaymentStatus("waiting");
        let paid;
        try {
            paid = await line.payment_interface.sendPaymentRequest(line);
        } catch (error) {
            line.handlePaymentResponse(false);
            throw error;
        }
        if (paid === null) {
            return;
        }
        line.handlePaymentResponse(paid);
        if (!paid || !order.toBeValidate() || !this.pos.config.auto_validate_electronic_payment || order.isRefundInProcess()) {
            return;
        }
        if (this._xpagoOnScreen(order)) {
            // The cashier may have left and come back: the payment screen on display validates.
            await this.pos.autoValidateOrder({ order });
            return;
        }
        // The money arrived while the cashier was on another sale or screen: the sale ends by itself in the
        // background (saved, receipt printed), without taking the register away from what the cashier is doing.
        await this._xpagoValidateInBackground(order, line.amount);
    },

    async _xpagoValidateInBackground(order, amount) {
        const money = this.pos.formatCurrency(amount);
        const sale = order.pos_reference || order.name || "";
        const validation = new OrderPaymentValidation(this.pos.getValidationOrderOptions({ order }));
        let ok = false;
        try {
            ok =
                (await validation.askBeforeValidation()) !== false &&
                (await validation._askForCustomerIfRequired()) !== false &&
                (await validation.isOrderValid(false));
            if (ok) {
                for (const payment of [...order.payment_ids]) {
                    if (!payment.isDone() || payment.amount === 0) {
                        order.removePaymentline(payment);
                    }
                }
                const result = await validation.finalizeValidation();
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
                            this.pos.navigate("PaymentScreen", { orderUuid: order.uuid });
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
            this.pos.router.currentScreen() === "PaymentScreen"
        );
    },

    async sendForceDone(line) {
        const terminal = line.payment_method_id?.payment_interface;
        if (line.payment_method_id?.payment_provider !== "xpago_spei" || !terminal) {
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
        return super.sendForceDone(...arguments);
    },
});
