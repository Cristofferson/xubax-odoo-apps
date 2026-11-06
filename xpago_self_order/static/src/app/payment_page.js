/** @odoo-module */

import { patch } from "@web/core/utils/patch";
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
        if (this.selectedPaymentMethod?.use_payment_terminal !== "xpago") {
            return super.startPayment(...arguments);
        }
        this.selfOrder.paymentError = false;
        try {
            const result = await this.rpc(`/kiosk/payment/${this.selfOrder.pos_config_id}/kiosk`, {
                order: this.selfOrder.currentOrder,
                access_token: this.selfOrder.access_token,
                payment_method_id: this.state.paymentMethodId,
            });
            this.selfOrder.updateOrderFromServer(result.order);
            this.xpagoCharge = {
                id: result.payment_status.xpago_charge_id,
                orderId: result.order.id,
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
                const { state } = await this.rpc(
                    "/pos-self-order/xpago-charge-status/",
                    {
                        access_token: this.selfOrder.access_token,
                        order_id: charge.orderId,
                        charge_id: charge.id,
                    },
                    { silent: true }
                );
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
            await this.rpc("/pos-self-order/xpago-cancel-charge/", {
                access_token: this.selfOrder.access_token,
                order_id: charge.orderId,
                charge_id: charge.id,
            }).catch(() => {});
        }
    },
});
