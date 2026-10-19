/**
 * XUBAX - Virtual seller: the cash register shows an alert when a customer at a kiosk
 * asks for a person.
 */
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(PosStore.prototype, {
    async initServerData() {
        await super.initServerData(...arguments);
        this.data.connectWebSocket("XB_VA_HANDOFF", (payload) => {
            this.dialog.add(AlertDialog, { title: payload.title, body: payload.body });
        });
    },
});
