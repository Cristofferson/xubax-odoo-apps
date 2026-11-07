import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { onWillUnmount } from "@odoo/owl";
import { PaymentPage } from "@pos_self_order/app/pages/payment_page/payment_page";
import { waitForCharge } from "@xpago/pos/app/charge_wait";

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
            this.xpagoWatchInactivity(this.xpagoCharge);
            this.xpagoPoll();
        } catch (error) {
            this.selfOrder.handleErrorNotification(error);
            this.selfOrder.paymentError = true;
        }
    },

    /** A customer who walks away must not leave the terminal waiting: after the kiosk's timeout the charge is
     *  cancelled and the terminal is free for the next one. */
    xpagoWatchInactivity(charge) {
        const seconds = this.selfOrder.config.xpago_kiosk_timeout;
        if (!(seconds > 0)) {
            return;
        }
        charge.timer = setTimeout(async () => {
            if (!charge.active) {
                return;
            }
            await this.xpagoStop(true);
            this.selfOrder.paymentError = true;
            this.selfOrder.notification.add(
                _t("The card was not paid in time. The terminal is free: try again when you are ready."),
                { type: "warning" }
            );
        }, seconds * 1000);
    },

    async xpagoPoll() {
        const charge = this.xpagoCharge;
        // The server pays the order and tells the kiosk through its payment status channel; asking here only
        // makes the server read the charge back.
        await waitForCharge(
            { state: "pending" },
            () =>
                rpc("/pos-self-order/xpago-charge-status/", {
                    access_token: this.selfOrder.access_token,
                    order_id: charge.orderId,
                    charge_id: charge.id,
                }),
            () => charge.active
        );
        charge.active = false;
        clearTimeout(charge.timer);
    },

    async xpagoStop(cancel) {
        const charge = this.xpagoCharge;
        if (!charge?.active) {
            return;
        }
        charge.active = false;
        clearTimeout(charge.timer);
        if (cancel) {
            await rpc("/pos-self-order/xpago-cancel-charge/", {
                access_token: this.selfOrder.access_token,
                order_id: charge.orderId,
                charge_id: charge.id,
            }).catch(() => {});
        }
    },
});
