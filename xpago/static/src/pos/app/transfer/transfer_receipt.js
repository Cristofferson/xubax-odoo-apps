/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Payment } from "@point_of_sale/app/store/models";

patch(Payment.prototype, {
    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        result.xpago_transfer = this.xpagoTransfer();
        return result;
    },
    /** Payments made by XPago transfer, and transfers given back: the receipt says which CLABE and operation they were. Odoo 17 keeps the
     *  CLABE and the operation in the XPago fields of the payment. */
    xpagoTransfer() {
        if (
            this.payment_method?.use_payment_terminal !== "xpago_spei" ||
            !this.amount ||
            !(this.xpago_card_no || this.transaction_id)
        ) {
            return false;
        }
        return {
            refund: this.amount < 0,
            amount: Math.abs(this.amount),
            clabe_last4: this.xpago_card_no || "",
            operation: this.xpago_reference || "",
            holder: this.cardholder_name || "",
        };
    },
});
