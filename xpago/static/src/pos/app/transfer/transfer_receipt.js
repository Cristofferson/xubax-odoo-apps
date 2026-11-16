import { patch } from "@web/core/utils/patch";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

patch(OrderReceipt.prototype, {
    /** Payments made by XPago transfer: the receipt says which CLABE and operation they were. */
    get xpagoTransferLines() {
        return this.paymentLines.filter(
            (line) =>
                line.payment_method_id?.use_payment_terminal === "xpago_spei" &&
                line.amount > 0 &&
                (line.card_no || line.transaction_id)
        );
    },
});
