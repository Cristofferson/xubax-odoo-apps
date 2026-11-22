/** @odoo-module */

import { _t } from "@web/core/l10n/translation";

/** Small helpers of the XPago transfer screen, kept apart so they can be tested on their own. */

export const TRANSFER_FINAL_STATES = ["paid", "cancelled", "returned"];

/** A CLABE as people read it aloud: bank (3) · city (3) · account (11) · check digit (1). */
export function formatClabe(clabe) {
    const digits = String(clabe || "").replace(/\D/g, "");
    if (digits.length !== 18) {
        return digits;
    }
    return [digits.slice(0, 3), digits.slice(3, 6), digits.slice(6, 17), digits.slice(17)].join(" ");
}

/** How often the register asks whether the money arrived: a transfer takes from seconds to minutes. */
export function transferDelay(elapsed) {
    if (elapsed < 60000) {
        return 3000;
    }
    return elapsed < 10 * 60000 ? 5000 : 10000;
}

/** Minutes left of the CLABE (0 once it expired), from the server time "YYYY-MM-DD HH:MM:SS" (UTC). */
export function minutesLeft(expiresAt, now = Date.now()) {
    const end = expiresAt ? Date.parse(expiresAt.replace(" ", "T") + "Z") : NaN;
    if (Number.isNaN(end)) {
        return null;
    }
    return Math.max(0, Math.ceil((end - now) / 60000));
}

/** The fields of the customer that XPago needs and the customer lacks: a name, a valid email, a phone of 10
 *  digits (``mobile`` counts as the phone). */
export function missingCustomerFields(partner) {
    const missing = [];
    if (!(partner?.name || "").trim()) {
        missing.push("name");
    }
    if (!/^\S+@\S+\.\S+$/.test((partner?.email || "").trim())) {
        missing.push("email");
    }
    if (String(partner?.phone || partner?.mobile || "").replace(/\D/g, "").length < 10) {
        missing.push("phone");
    }
    return missing;
}

/** What XPago needs of who pays and the customer lacks: their name, a valid email, a phone of 10 digits. */
export function missingCustomerData(partner) {
    const labels = { name: _t("name"), email: _t("email"), phone: _t("phone") };
    return missingCustomerFields(partner).map((field) => labels[field]);
}

/** A phone for wa.me: digits only, and a Mexican 10-digit number gets the country code 52. */
export function whatsappPhone(phone) {
    const digits = String(phone || "").replace(/\D/g, "");
    if (digits.length === 10) {
        return "52" + digits;
    }
    return digits.length >= 11 ? digits : "";
}

/** The transfer details as a WhatsApp message, so the customer can copy the CLABE in their bank app. */
export function whatsappText(view, { amountText, clabeText, minutes }) {
    const lines = [
        _t("Payment by transfer to %s", view.business),
        "",
        _t("Exact amount: %s", amountText),
        _t("CLABE: %s", view.clabe),
        _t("Bank: %s", view.bank),
        _t("Beneficiary: %s", view.beneficiary),
    ];
    if (view.concept) {
        lines.push(_t("Concept (optional): %s", view.concept));
    }
    if (minutes) {
        lines.push(_t("Valid for %s min", minutes));
    }
    lines.push("", _t("CLABE in parts: %s", clabeText));
    return lines.join("\n");
}

/** The wa.me link: to the customer's phone when we have it, else WhatsApp asks whom to send it to. */
export function whatsappUrl(phone, text) {
    const number = whatsappPhone(phone);
    return `https://wa.me/${number}?text=${encodeURIComponent(text)}`;
}
