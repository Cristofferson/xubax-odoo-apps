import { Component, proxy, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { session } from "@web/session";
import { useService } from "@web/core/utils/hooks";

const TOKEN_KEY = "xpago.reader.token";
const NAME_KEY = "xpago.reader.name";

/** A random key, made once in this browser: the codes read on the terminal reach only the screen that made it. */
export function readerToken(key) {
    let token = browser.localStorage.getItem(key);
    if (!token) {
        const bytes = new Uint8Array(12);
        window.crypto.getRandomValues(bytes);
        token = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
        browser.localStorage.setItem(key, token);
    }
    return token;
}

/** The pairing QR the terminal scans; it names the screen so the terminal shows that name. */
export function readerLink(token, name) {
    const params = new URLSearchParams({ token, db: session.db || "", name: name || "", kind: "screen" });
    return `${browser.location.origin}/xpago/reader/link?${params}`;
}

export function qrSrc(url) {
    return `/report/barcode/?barcode_type=QR&value=${encodeURIComponent(url)}&width=320&height=320`;
}

export class XpagoBackendReaderDialog extends Component {
    static template = "xpago.BackendReaderDialog";
    static components = { Dialog };
    props = useProps({ close: t.function() });

    setup() {
        this.state = proxy({ name: browser.localStorage.getItem(NAME_KEY) || "" });
    }

    onName(ev) {
        this.state.name = ev.target.value.trim().slice(0, 40);
        browser.localStorage.setItem(NAME_KEY, this.state.name);
    }

    get qrSrc() {
        return qrSrc(readerLink(readerToken(TOKEN_KEY), this.state.name));
    }
}

/**
 * Codes read on an XPago terminal paired with this browser arrive as if they were read here: every Odoo screen that
 * reads barcodes (Barcode, Inventory, Manufacturing, Repairs…) gets them through the barcode service.
 */
export const xpagoReaderService = {
    dependencies: ["bus_service", "barcode"],
    start(env, { bus_service, barcode }) {
        const token = browser.localStorage.getItem(TOKEN_KEY);
        if (token) {
            bus_service.addChannel(`xpago_reader_${token}`);
        }
        bus_service.subscribe("xpago_reader_scan", (payload) => {
            if (payload?.barcode) {
                barcode.bus.trigger("barcode_scanned", {
                    barcode: payload.barcode,
                    target: document.activeElement || document.body,
                });
            }
        });
        bus_service.start();
    },
};

registry.category("services").add("xpago_reader", xpagoReaderService);

function xpagoReaderItem() {
    const busService = useService("bus_service");
    const dialog = useService("dialog");
    return {
        type: "item",
        id: "xpago_reader",
        description: _t("Pair XPago reader"),
        callback: () => {
            busService.addChannel(`xpago_reader_${readerToken(TOKEN_KEY)}`);
            dialog.add(XpagoBackendReaderDialog, {});
        },
        sequence: 66,
    };
}

registry.category("user_menuitems").add("xpago_reader", xpagoReaderItem);
