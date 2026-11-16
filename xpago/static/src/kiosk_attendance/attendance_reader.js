import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { startKioskReader } from "@xpago/kiosk/reader_kiosk";

/** The attendance kiosk gets the badges read on an XPago terminal; its key is in its own address. */
registry.category("services").add("xpago_reader_attendance", {
    dependencies: ["barcode"],
    start(env, { barcode }) {
        const match = browser.location.pathname.match(/^\/hr_attendance\/([^/?#]+)/);
        if (match) {
            startKioskReader(barcode, { kiosk: "attendance", key: match[1] });
        }
    },
});
