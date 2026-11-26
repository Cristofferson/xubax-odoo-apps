import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async initServerData() {
        const result = await super.initServerData(...arguments);
        // Codes read on an XPago terminal linked to this register arrive through the POS bus.
        this.data.connectWebSocket("XPAGO_READER_SCAN", (payload) => this.xpagoOnReaderScan(payload));
        return result;
    },
    xpagoOnReaderScan(payload) {
        if (payload?.barcode && this.barcodeReader) {
            this.barcodeReader.scan(payload.barcode);
        }
    },
});
