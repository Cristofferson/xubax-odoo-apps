/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { Payment } from "@point_of_sale/app/store/models";

// The card of an XPago payment, as the voucher of the receipt prints it (see pos.payment).
const XPAGO_CARD_FIELDS = [
    "xpago_card_brand",
    "xpago_card_no",
    "xpago_issuer_bank",
    "xpago_authorization",
    "xpago_reference",
    "xpago_entry_mode",
    "xpago_terms",
    "xpago_tip",
];

patch(Payment.prototype, {
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        for (const name of XPAGO_CARD_FIELDS) {
            this[name] = json[name] || false;
        }
    },
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        for (const name of XPAGO_CARD_FIELDS) {
            json[name] = this[name] || false;
        }
        return json;
    },
    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        result.xpago_voucher = this.xpagoVoucher();
        return result;
    },
    /** The card voucher this payment prints in the receipt (terminals that print with the point of sale), or
     *  false: only positive card payments of XPago terminals. */
    xpagoVoucher() {
        const config = this.pos.config;
        if (
            !config.xpago_voucher_on_receipt ||
            this.payment_method?.use_payment_terminal !== "xpago" ||
            !(this.amount > 0) ||
            !(this.xpago_card_no || this.xpago_authorization)
        ) {
            return false;
        }
        // Odoo 17 keeps the brand and the funding of the card together in its type ("VISA CREDIT").
        const type = (this.card_type || "").toUpperCase();
        const debit = type.includes("DEBIT");
        return {
            brand: this.xpago_card_brand || "",
            card_no: this.xpago_card_no || "",
            funding: debit ? _t("Debit") : type.includes("CREDIT") ? _t("Credit") : "",
            bank: this.xpago_issuer_bank || "",
            authorization: this.xpago_authorization || "",
            // The operation the processor gave; its internal id (transaction_id) stays out of the ticket.
            operation: this.xpago_reference || "",
            entry_mode: this.xpago_entry_mode || "",
            merchant: config.xpago_voucher_merchant || "",
            terms: this.xpago_terms > 1 ? this.xpago_terms : false,
            tip: this.xpago_tip || 0,
            legend: (debit ? config.xpago_voucher_debit_text : config.xpago_voucher_credit_text) || "",
            // Chip and contactless are verified by PIN or need nothing: only a swiped or keyed card is signed.
            signature:
                Boolean(config.xpago_voucher_signature) &&
                !["CHIP", "CONTACTLESS"].includes((this.xpago_entry_mode || "").toUpperCase()),
        };
    },
});
