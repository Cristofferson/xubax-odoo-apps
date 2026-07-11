import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";

export class XbDeliveryButton extends Component {
    static template = "xb_pos_delivery.DeliveryButton";
    static props = {};

    setup() {
        this.pos = usePos();
    }

    onClick() {
        this.pos.xbStopDeliverySound();
        this.pos.xbOpenDeliveryDialog();
    }

    get newCount() {
        return this.pos.xbDelivery?.total_new || 0;
    }
}

patch(Navbar, {
    components: { ...Navbar.components, XbDeliveryButton },
});
