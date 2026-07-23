/** "Recargas" button in the product-screen control bar. Opens the TAECEL sale
 *  flow. Hidden when no TAECEL account is loaded for the POS. */
import { Component } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { usePos, ControlButtons } from "../compat";

export class XbTaecelControlButton extends Component {
    static template = "xb_pos_taecel.ControlButton";
    /** The POS hands us its own button classes so we look like a native control
     *  button in whatever panel we land in (they differ between the compact bar
     *  and the expanded "More" panel, and between Odoo versions). */
    static props = { buttonClass: { type: String, optional: true } };
    static defaultProps = { buttonClass: "btn btn-secondary btn-lg py-5" };

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
