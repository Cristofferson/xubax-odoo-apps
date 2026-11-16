/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosBus } from "@point_of_sale/app/bus/pos_bus_service";

/** Codes read on an XPago terminal linked to this register arrive through the bus, on a channel named with the
 *  register's own secret (Odoo 17: see controllers/reader.py). */
patch(PosBus.prototype, {
    setup(env, { pos, bus_service }) {
        super.setup(...arguments);
        const token = pos.config.access_token;
        if (token) {
            bus_service.addChannel(`xpago_reader_pos_${pos.config.id}_${token}`);
        }
    },
    dispatch(message) {
        super.dispatch(...arguments);
        if (message.type === "XPAGO_READER_SCAN") {
            this.xpagoOnReaderScan(message.payload);
        }
    },
    xpagoOnReaderScan(payload) {
        if (payload?.barcode && this.pos.barcodeReader) {
            this.pos.barcodeReader.scan(payload.barcode);
        }
    },
});
