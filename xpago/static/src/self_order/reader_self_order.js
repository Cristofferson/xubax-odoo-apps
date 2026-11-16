import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { startKioskReader } from "@xpago/kiosk/reader_kiosk";

/**
 * The self-order kiosk adds the products read on an XPago terminal. Only in kiosk mode: the same screens also open
 * on customers' phones (order from the table), which never get codes.
 */
registry.category("services").add("xpago_reader_self_order", {
    dependencies: ["barcode", "self_order"],
    start(env, { barcode, self_order }) {
        const wait = () => {
            if (!self_order.config) {
                browser.setTimeout(wait, 1000);
            } else if (self_order.config.self_ordering_mode === "kiosk") {
                startKioskReader(barcode, {
                    kiosk: "self_order",
                    config_id: self_order.config.id,
                    access_token: self_order.config.access_token,
                });
            }
        };
        wait();
    },
});
