import { rpc } from "@web/core/network/rpc";
import { browser } from "@web/core/browser/browser";

/**
 * Kiosks that open without a user (attendance, self-order) get the codes read on an XPago terminal: the terminal
 * picks the kiosk from its own list, and the kiosk asks every two seconds for its codes, proving which kiosk it is
 * with its own secret, then hands them to Odoo's barcode service as if its own reader read them. Nothing is shown.
 */
const POLL_MS = 2000;

export function startKioskReader(barcode, identity) {
    let last = 0;
    const poll = async () => {
        try {
            const answer = await rpc("/xpago/reader/pull", { ...identity, last }, { silent: true });
            if (last) {
                for (const code of answer.codes) {
                    barcode.bus.trigger("barcode_scanned", { barcode: code, target: document.body });
                }
            }
            last = answer.last;
        } catch {
            // No connection for a moment: the next round asks again.
        }
        browser.setTimeout(poll, POLL_MS);
    };
    poll();
}
