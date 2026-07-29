/** @odoo-module **/
// XUBAX - Jewelry Repairs & Workshop, Point of Sale bridge.
// Adds one button to the product screen. Everything the counter needs lives
// behind it, because the floor staff should never have to leave the register.

import { patch } from "@web/core/utils/patch";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { JewelryDialog } from "@xb_jewelry_service_pos/app/screens/jewelry_dialog";

patch(ControlButtons.prototype, {
    xbOpenJewelry() {
        this.dialog.add(JewelryDialog, {
            getPartner: () => this.pos.getOrder()?.getPartner(),
            getOrder: () => this.pos.getOrder(),
        });
    },
});
