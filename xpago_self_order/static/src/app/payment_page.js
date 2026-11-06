import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { onWillUnmount } from "@odoo/owl";
import { PaymentPage } from "@pos_self_order/app/pages/payment_page/payment_page";

const POLL_DELAY = 2000;

patch(PaymentPage.prototype, {
    setup() {
        super.setup(...arguments);
        this.xpagoCharge = null;
        onWillUnmount(() => this.xpagoStop(true));
    },

    async startPayment() {
        if (this.selectedPaymentMethod?.payment_provider !== "xpago") {
            return super.startPayment(...arguments);
        }
        this.selfOrder.paymentError = false;
        try {
            const result = await rpc(`/kiosk/payment/${this.selfOrder.config.id}/kiosk`, {
                order: this.selfOrder.currentOrder.serializeForORM(),
                access_token: this.selfOrder.access_token,
                payment_method_id: this.state.paymentMethodId,
            });
            this.xpagoCharge = {
                id: result.payment_status.xpago_charge_id,
                orderId: result.order[0].id,
                active: true,
            };
            this.xpagoPoll();
        } catch (error) {
            this.selfOrder.handleErrorNotification(error);
            this.selfOrder.paymentError = true;
        }
    },

    async xpagoPoll() {
        const charge = this.xpagoCharge;
        while (charge?.active) {
            await new Promise((resolve) => setTimeout(resolve, POLL_DELAY));
            if (!charge.active) {
                return;
            }
            try {
                const { state } = await rpc("/pos-self-order/xpago-charge-status/", {
                    access_token: this.selfOrder.access_token,
                    order_id: charge.orderId,
                    charge_id: charge.id,
                });
                // The server pays the order and tells the kiosk through its payment status channel.
                if (["confirmed", "cancelled", "expired"].includes(state)) {
                    charge.active = false;
                }
            } catch {
                // A lost connection is not an answer: keep asking.
            }
        }
    },

    async xpagoStop(cancel) {
        const charge = this.xpagoCharge;
        if (!charge?.active) {
            return;
        }
        charge.active = false;
        if (cancel) {
            await rpc("/pos-self-order/xpago-cancel-charge/", {
                access_token: this.selfOrder.access_token,
                order_id: charge.orderId,
                charge_id: charge.id,
            }).catch(() => {});
        }
    },
});
