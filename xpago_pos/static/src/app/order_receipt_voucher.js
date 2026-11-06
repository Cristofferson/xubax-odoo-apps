import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

patch(OrderReceipt.prototype, {
    /** Card payments of XPago terminals, whose voucher goes in this receipt. */
    get xpagoVoucherLines() {
        if (!this.order.config.xpago_voucher_on_receipt) {
            return [];
        }
        return this.paymentLines.filter(
            (line) =>
                line.payment_method_id?.use_payment_terminal === "xpago" &&
                line.amount > 0 &&
                (line.card_no || line.transaction_id)
        );
    },
    xpagoIsDebit(line) {
        return (line.card_type || "").toUpperCase().includes("DEBIT");
    },
    xpagoFunding(line) {
        const type = (line.card_type || "").toUpperCase();
        if (type.includes("DEBIT")) {
            return _t("Debit");
        }
        return type.includes("CREDIT") ? _t("Credit") : "";
    },
    /** Chip and contactless cards are verified by PIN or need nothing: only a swiped or keyed card is signed. */
    xpagoNeedsSignature(line) {
        const mode = (line.payment_method_payment_mode || "").toUpperCase();
        return this.order.config.xpago_voucher_signature && !["CHIP", "CONTACTLESS"].includes(mode);
    },
    xpagoLegend(line) {
        const config = this.order.config;
        return (
            (this.xpagoIsDebit(line) ? config.xpago_voucher_debit_text : config.xpago_voucher_credit_text) || ""
        );
    },
});
