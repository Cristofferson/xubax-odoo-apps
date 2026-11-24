import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { takenPaymentIds } from "@xpago/pos/app/payment_xpago";

/** «Force done» on an XPago line asks XPago first: the sale is only marked paid when XPago approved its card charge,
 *  so a charge cancelled on the terminal never closes a sale as paid. */
patch(PaymentScreen.prototype, {
    async sendForceDone(line) {
        const terminal = line.payment_method_id?.payment_terminal;
        if (line.payment_method_id?.use_payment_terminal !== "xpago" || !terminal) {
            return super.sendForceDone(...arguments);
        }
        const tell = (body) => this.dialog.add(AlertDialog, { title: _t("XPago"), body });
        if (line.amount < 0) {
            tell(_t("A refund is only completed when XPago confirms it. Wait for it, or press Cancel and pay it back another way."));
            return;
        }
        let charge;
        try {
            charge = await terminal._call("xpago_force_check", [
                {
                    order_uuid: line.pos_order_id.uuid,
                    amount: line.amount,
                    taken_payment_ids: takenPaymentIds(line.pos_order_id, line),
                },
            ]);
        } catch {
            tell(_t("Could not ask XPago whether this card was paid. Check the connection and try again."));
            return;
        }
        if (charge.state !== "confirmed") {
            tell(
                charge.state === "pending"
                    ? _t("XPago has not received the payment of this charge yet. Wait for the customer to pay, or press Cancel.")
                    : _t("XPago says this charge was not paid. It is not marked as paid: charge it again or take another payment.")
            );
            return;
        }
        const pending = terminal.charges[line.uuid];
        if (pending) {
            // The register is still waiting for this charge: its next look finds it approved and completes the line
            // with the card and the tip, as usual.
            pending.forced = charge;
            this.notification.add(_t("XPago approved this charge: it is completed in a moment."), { type: "info" });
            return;
        }
        Object.assign(line, charge.payment);
        return super.sendForceDone(...arguments);
    },
});
