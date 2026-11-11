import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/** The card voucher of the XPago terminals in the receipt: a copy of the Python side (receipt/pos_order_receipt.py). */
patch(GeneratePrinterData.prototype, {
    generatePaymentData() {
        const data = super.generatePaymentData(...arguments);
        // On the terminal's own printer the terminal adds its certified voucher under this receipt.
        const voucher =
            Boolean(this.config.xpago_voucher_on_receipt) && !this.config.xpago_print_on_terminal;
        this.order.payment_ids.forEach((line, index) => {
            const cardType = (line.card_type || "").toUpperCase();
            Object.assign(data[index], {
                xpago_voucher:
                    voucher &&
                    line.payment_method_id?.payment_provider === "xpago" &&
                    line.amount > 0 &&
                    Boolean(line.card_no || line.transaction_id),
                xpago_debit: cardType.includes("DEBIT"),
                xpago_credit: cardType.includes("CREDIT") && !cardType.includes("DEBIT"),
                xpago_signature:
                    Boolean(this.config.xpago_voucher_signature) &&
                    !["CHIP", "CONTACTLESS"].includes((line.payment_method_payment_mode || "").toUpperCase()),
            });
        });
        return data;
    },
});
