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

/** Who pays, to prefill the form: the customer of the sale, else the business itself. */
export function customerDefaults(partner, company) {
    const source = partner && (partner.email || partner.phone) ? partner : null;
    return {
        name: (source || partner)?.name || "",
        email: source?.email || company?.email || "",
        phone: source?.phone || company?.phone || "",
        isBusiness: !source,
    };
}
