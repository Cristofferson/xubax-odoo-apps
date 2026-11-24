import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    /** The receipt is drawn from this export (also when it is reprinted, emailed or sent by WhatsApp), so the
     *  payments made by XPago transfer travel in it: the receipt says which CLABE and operation they were. */
    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        result.xpago_transfers = this.payment_ids
            .filter(
                (line) =>
                    !line.is_change &&
                    line.payment_method_id?.use_payment_terminal === "xpago_spei" &&
                    line.get_amount() !== 0 &&
                    (line.card_no || line.transaction_id)
            )
            .map((line) => ({
                uuid: line.uuid,
                card_no: line.card_no || "",
                operation: line.payment_ref_no || "",
                payer: line.cardholder_name || "",
                // A transfer given back with a refund says so.
                refund: line.get_amount() < 0,
                amount: Math.abs(line.get_amount()),
            }));
        return result;
    },
});
