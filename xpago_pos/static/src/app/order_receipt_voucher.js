import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    /** The receipt is drawn from this export (also when it is reprinted, emailed or sent by WhatsApp), so the
     *  vouchers of the cards charged on XPago terminals travel in it. */
    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        result.xpago_vouchers = this.xpagoVouchers();
        return result;
    },

    xpagoVouchers() {
        const config = this.config;
        if (!config.xpago_voucher_on_receipt) {
            return [];
        }
        return this.payment_ids
            .filter(
                (line) =>
                    !line.is_change &&
                    line.payment_method_id?.use_payment_terminal === "xpago" &&
                    line.get_amount() > 0 &&
                    (line.card_no || line.transaction_id)
            )
            .map((line) => {
                const type = (line.card_type || "").toUpperCase();
                const debit = type.includes("DEBIT");
                return {
                    uuid: line.uuid,
                    card_brand: line.card_brand || "",
                    card_no: line.card_no || "",
                    funding: debit ? _t("Debit") : type.includes("CREDIT") ? _t("Credit") : "",
                    bank: line.payment_method_issuer_bank || "",
                    authorization: line.payment_method_authcode || "",
                    // The operation the processor gave; its internal id (transaction_id) stays out of the ticket.
                    operation: line.payment_ref_no || "",
                    entry_mode: line.payment_method_payment_mode || "",
                    merchant: config.xpago_voucher_merchant || "",
                    amount: line.get_amount(),
                    legend: (debit ? config.xpago_voucher_debit_text : config.xpago_voucher_credit_text) || "",
                    // Chip and contactless are verified by PIN or need nothing: only a swiped or keyed card is signed.
                    signature:
                        Boolean(config.xpago_voucher_signature) &&
                        !["CHIP", "CONTACTLESS"].includes((line.payment_method_payment_mode || "").toUpperCase()),
                };
            });
    },
});
