/** @odoo-module */
/** "Recargas" button in the product-screen control bar (Odoo 17). Opens the
 *  TAECEL sale flow; shown only when a TAECEL account is loaded for the POS. */
import { Component } from "@odoo/owl";
import { usePos, ProductScreen } from "../compat";

export class XbTaecelControlButton extends Component {
    static template = "xb_pos_taecel.ControlButton";

    setup() {
        this.pos = usePos();
    }

    onClick() {
        this.pos.xbOpenTaecelSale();
    }
}

ProductScreen.addControlButton({
    component: XbTaecelControlButton,
    condition: function () {
        return this.pos.xbTaecelEnabled;
    },
});
