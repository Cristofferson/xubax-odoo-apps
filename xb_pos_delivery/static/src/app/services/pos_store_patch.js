import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { _t } from "@web/core/l10n/translation";
import { XbDeliveryOrdersDialog } from "@xb_pos_delivery/app/popup/delivery_orders_popup";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.xbDelivery = {
            counts: {},
            providers: [],
            total_new: 0,
        };
        this.xbSoundPlaying = false;
        if (this.xbDeliveryEnabled) {
            this.data.connectWebSocket("XB_DELIVERY_ORDER", (data) =>
                this.xbOnDeliveryEvent(data)
            );
            this.data.connectWebSocket("XB_DELIVERY_STORE", (data) => {
                this.notification.add(
                    data.online
                        ? _t("Store is now online on %s.", data.provider)
                        : _t("Store is now offline on %s.", data.provider),
                    { type: data.online ? "success" : "warning" }
                );
            });
            await this.xbRefreshDeliveryData();
        }
    },

    get xbDeliveryEnabled() {
        return (this.models["xb.delivery.account"]?.length || 0) > 0;
    },

    get xbDeliveryOrders() {
        return this.models["pos.order"]
            .filter((o) => o.xb_delivery_account_id && o.state !== "cancel")
            .sort((a, b) => {
                const rank = { placed: 0, accepted: 1, ready: 2, dispatched: 3 };
                const ra = rank[a.xb_delivery_status] ?? 9;
                const rb = rank[b.xb_delivery_status] ?? 9;
                return ra - rb || b.id - a.id;
            });
    },

    async xbLoadDeliveryOrders() {
        const accountIds = this.models["xb.delivery.account"].map((a) => a.id);
        if (!accountIds.length) {
            return;
        }
        try {
            await this.data.loadServerOrders([
                ["session_id", "=", this.session.id],
                ["state", "=", "draft"],
                ["xb_delivery_account_id", "in", accountIds],
            ]);
        } catch {
            this.notification.add(_t("Could not load delivery orders."), {
                type: "warning",
            });
        }
    },

    async xbRefreshDeliveryData() {
        await this.xbLoadDeliveryOrders();
        this.xbDelivery = await this.data.call(
            "pos.config",
            "get_xb_delivery_data",
            [this.config.id]
        );
    },

    async xbOnDeliveryEvent(data) {
        await this.xbRefreshDeliveryData();
        const order = data.order_id
            ? this.models["pos.order"].get(data.order_id)
            : null;
        if (data.status === "placed") {
            if (!this.xbSoundPlaying) {
                this.xbSoundPlaying = true;
                this.sound.play("order-receive-tone", { loop: true, volume: 1 });
            }
            this.xbCloseNotification = this.notification.add(
                _t("New delivery order received."),
                {
                    type: "success",
                    sticky: true,
                    buttons: [
                        {
                            name: _t("Review"),
                            onClick: () => {
                                this.xbStopDeliverySound();
                                this.xbCloseNotification?.();
                                this.xbOpenDeliveryDialog();
                            },
                        },
                    ],
                    onClose: () => this.xbStopDeliverySound(),
                }
            );
        } else if (data.status === "cancelled" && order) {
            this.notification.add(
                _t("Delivery order %s was cancelled by the platform.",
                    order.xb_delivery_display_id || ""),
                { type: "danger", sticky: true }
            );
        }
    },

    xbStopDeliverySound() {
        if (this.xbSoundPlaying) {
            this.sound.stop("order-receive-tone");
            this.xbSoundPlaying = false;
        }
    },

    xbOpenDeliveryDialog() {
        this.dialog.add(XbDeliveryOrdersDialog);
    },

    async xbOrderAction(order, method, args = []) {
        await this.data.call("pos.order", method, [[order.id], ...args]);
        await this.xbRefreshDeliveryData();
    },
});
