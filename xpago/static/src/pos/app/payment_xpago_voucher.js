import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/** The card voucher of the XPago terminals and the CLABE of the XPago transfers in the receipt: a copy of the Python side (receipt/pos_order_receipt.py). */
patch(GeneratePrinterData.prototype, {
    generatePaymentData() {
        const data = super.generatePaymentData(...arguments);
        // On the terminal's own printer the terminal adds its certified voucher under this receipt.
        const voucher =
            Boolean(this.config.xpago_voucher_on_receipt) && !this.config.xpago_print_on_terminal;
        this.order.payment_ids.forEach((line, index) => {
            const cardType = (line.card_type || "").toUpperCase();
            // A refund paid back to the card or by transfer: the customer keeps the proof of where the money goes.
            const refund = line.amount < 0;
            Object.assign(data[index], {
                xpago_voucher:
                    voucher &&
                    line.payment_method_id?.payment_provider === "xpago" &&
                    line.amount !== 0 &&
                    Boolean(line.card_no || line.transaction_id),
                xpago_transfer:
                    line.payment_method_id?.payment_provider === "xpago_spei" &&
                    line.amount !== 0 &&
                    Boolean(line.card_no || line.transaction_id),
                xpago_terms: line.xpago_terms > 1 ? line.xpago_terms : 0,
                xpago_debit: cardType.includes("DEBIT"),
                xpago_credit: cardType.includes("CREDIT") && !cardType.includes("DEBIT"),
                xpago_refund: refund,
                xpago_amount: refund
                    ? this.formatCurrency(Math.abs(line.amount_currency || line.amount), line.currency)
                    : data[index].amount,
                xpago_signature:
                    !refund &&
                    Boolean(this.config.xpago_voucher_signature) &&
                    !["CHIP", "CONTACTLESS"].includes((line.payment_method_payment_mode || "").toUpperCase()),
            });
        });
        return data;
    },
});
