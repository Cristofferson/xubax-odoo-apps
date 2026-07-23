/** "Recargas" button in the product-screen control bar. Opens the TAECEL sale
 *  flow. Hidden when no TAECEL account is loaded for the POS. */
import { Component } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { usePos, ControlButtons } from "../compat";

export class XbTaecelControlButton extends Component {
    static template = "xb_pos_taecel.ControlButton";
    static props = {};

    setup() {
        this.pos = usePos();
    }

    get isAvailable() {
        return this.pos.xbTaecelEnabled;
    }

    onClick() {
        this.pos.xbOpenTaecelSale();
    }
}

patch(ControlButtons, {
    components: { ...ControlButtons.components, XbTaecelControlButton },
});
