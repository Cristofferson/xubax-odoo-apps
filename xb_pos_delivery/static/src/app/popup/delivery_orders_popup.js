import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export class XbDeliveryOrdersDialog extends Component {
    static template = "xb_pos_delivery.DeliveryOrdersDialog";
    static components = { Dialog };
    static props = { close: Function };

    setup() {
        this.pos = usePos();
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({ busyOrderId: null });
    }

    get orders() {
        return this.pos.xbDeliveryOrders;
    }

    providerName(order) {
        const account = order.xb_delivery_account_id;
        const provider =
            (account && account.provider) || order.xb_delivery_provider || "";
        return provider === "uber_eats"
            ? "Uber Eats"
            : provider === "didi_food"
              ? "DiDi Food"
              : provider;
    }

    providerClass(order) {
        const account = order.xb_delivery_account_id;
        return "xb-" + ((account && account.provider) || order.xb_delivery_provider || "");
    }

    statusLabel(order) {
        const labels = {
            placed: _t("New"),
            accepted: _t("Preparing"),
            ready: _t("Ready"),
            dispatched: _t("On the way"),
            delivered: _t("Delivered"),
            cancelled: _t("Cancelled"),
        };
        return labels[order.xb_delivery_status] || order.xb_delivery_status || "";
    }

    courier(order) {
        const raw = order.xb_courier_json;
        if (!raw) {
            return null;
        }
        try {
            const data = typeof raw === "string" ? JSON.parse(raw) : raw;
            return data && data.name ? data : null;
        } catch {
            return null;
        }
    }

    async runAction(order, method, args = []) {
        this.state.busyOrderId = order.id;
        try {
            await this.pos.xbOrderAction(order, method, args);
        } catch (error) {
            this.notification.add(
                error?.data?.message || _t("The platform call failed."),
                { type: "danger", sticky: true }
            );
        } finally {
            this.state.busyOrderId = null;
        }
    }

    accept(order) {
        return this.runAction(order, "action_xb_accept");
    }

    ready(order) {
        return this.runAction(order, "action_xb_ready");
    }

    reject(order) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Reject order"),
            body: _t(
                "Reject order %s on %s? The customer will be notified by the platform.",
                order.xb_delivery_display_id || "",
                this.providerName(order)
            ),
            confirm: () => this.runAction(order, "action_xb_reject"),
            cancel: () => {},
        });
    }

    viewOrder(order) {
        this.props.close();
        this.pos.setOrder(order);
        this.pos.navigate("TicketScreen", {
            stateOverride: { filter: "ACTIVE_ORDERS" },
        });
    }
}
