/** @odoo-module */

import { registry } from "@web/core/registry";
import { startKioskReader } from "@xpago/kiosk/reader_kiosk";

/**
 * The self-order kiosk adds the products read on an XPago terminal. Only in kiosk mode: the same screens also open
 * on customers' phones (order from the table), which never get codes. Odoo 17: the self-order service is ready
 * (its data loaded) when it is handed over.
 */
registry.category("services").add("xpago_reader_self_order", {
    dependencies: ["barcode", "self_order"],
    start(env, { barcode, self_order }) {
        if (self_order.config?.self_ordering_mode === "kiosk" && self_order.access_token) {
            startKioskReader(barcode, {
                kiosk: "self_order",
                config_id: self_order.pos_config_id,
                access_token: self_order.access_token,
            });
        }
    },
});
