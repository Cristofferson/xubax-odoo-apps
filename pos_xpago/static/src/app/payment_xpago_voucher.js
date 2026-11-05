import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/** The card voucher of the XPago terminals in the receipt: a copy of the Python side (receipt/pos_order_receipt.py). */
patch(GeneratePrinterData.prototype, {
    generatePaymentData() {
        const data = super.generatePaymentData(...arguments);
        const voucher = Boolean(this.config.xpago_voucher_on_receipt);
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
            });
        });
        return data;
    },
});
