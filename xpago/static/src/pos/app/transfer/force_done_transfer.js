import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PosPaymentMethod } from "@point_of_sale/app/models/pos_payment_method";

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
    /** The money may arrive long after, while the cashier is on another sale: only that sale is validated. */
    async sendPaymentRequest(line) {
        if (line.payment_method_id?.payment_provider !== "xpago_spei") {
            return super.sendPaymentRequest(...arguments);
        }
        this.numberBuffer.capture();
        const order = line.pos_order_id;
        const paid = await line.pay();
        if (
            paid &&
            this.pos.getOrder() === order &&
            this.pos.router.currentScreen() === "PaymentScreen"
        ) {
            await this.pos.autoValidateOrder({ order });
        }
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
