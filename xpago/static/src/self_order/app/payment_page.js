import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { onWillUnmount, useState } from "@odoo/owl";
import { PaymentPage } from "@pos_self_order/app/pages/payment_page/payment_page";
import { waitForCharge } from "@xpago/pos/app/charge_wait";
import { TRANSFER_FINAL_STATES, formatClabe, minutesLeft, transferDelay } from "@xpago/pos/app/transfer/transfer_utils";

/** XPago does not make a CLABE for less than this (the processor answers «bank_transfer_not_offered»). */
export const XPAGO_SPEI_MINIMUM = 200;

patch(PaymentPage.prototype, {
    setup() {
        super.setup(...arguments);
        this.xpagoCharge = null;
        this.xpagoTransfer = useState({ step: null, name: "", phone: "", email: "", view: null, busy: false, now: Date.now() });
        this.xpagoTransferRun = null;
        const clock = setInterval(() => (this.xpagoTransfer.now = Date.now()), 15000);
        onWillUnmount(() => {
            clearInterval(clock);
            this.xpagoStop(true);
            this.xpagoTransferStop(true);
        });
    },

    get xpagoIsTransfer() {
        return this.selectedPaymentMethod?.use_payment_terminal === "xpago_spei";
    },

    async startPayment() {
        if (this.xpagoIsTransfer) {
            return this.xpagoTransferAsk();
        }
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

    // === TRANSFER (SPEI) === //

    get xpagoTransferAmount() {
        return this.selfOrder.currentOrder.priceIncl || 0;
    },

    get xpagoClabeText() {
        return formatClabe(this.xpagoTransfer.view?.clabe);
    },

    get xpagoMinutesLeft() {
        const run = this.xpagoTransferRun;
        const seconds = this.selfOrder.config.xpago_kiosk_transfer_timeout;
        if (run?.startedAt && seconds > 0) {
            return Math.max(0, Math.ceil((run.startedAt + seconds * 1000 - this.xpagoTransfer.now) / 60000));
        }
        return minutesLeft(this.xpagoTransfer.view?.expires_at, this.xpagoTransfer.now);
    },

    get xpagoQrUrl() {
        const url = this.xpagoTransfer.view?.checkout_url;
        return url ? `/report/barcode?barcode_type=QR&value=${encodeURIComponent(url)}&width=240&height=240` : "";
    },

    xpagoMoney(value) {
        return this.selfOrder.formatMonetary(value || 0);
    },

    /** First who pays: XPago makes the CLABE out to them. */
    xpagoTransferAsk() {
        this.selfOrder.paymentError = false;
        if (this.xpagoTransferAmount < XPAGO_SPEI_MINIMUM) {
            this.selfOrder.notification.add(
                _t("Payment by transfer is for purchases of %s or more.", this.xpagoMoney(XPAGO_SPEI_MINIMUM)),
                { type: "warning" }
            );
            this.xpagoTransferBack();
            return;
        }
        this.xpagoTransfer.view = null;
        this.xpagoTransfer.step = "form";
    },

    xpagoTransferMissing() {
        const t = this.xpagoTransfer;
        const missing = [];
        if (!t.name.trim()) {
            missing.push(_t("your name"));
        }
        if (t.phone.replace(/\D/g, "").length < 10) {
            missing.push(_t("a phone of 10 digits"));
        }
        if (!/^\S+@\S+\.\S+$/.test(t.email.trim())) {
            missing.push(_t("a valid email"));
        }
        return missing;
    },

    async xpagoTransferSubmit() {
        const t = this.xpagoTransfer;
        const missing = this.xpagoTransferMissing();
        if (missing.length) {
            this.selfOrder.notification.add(_t("Missing: %s.", missing.join(", ")), { type: "warning" });
            return;
        }
        if (t.busy) {
            return;
        }
        t.busy = true;
        try {
            const result = await rpc("/pos-self-order/xpago-transfer-start/", {
                access_token: this.selfOrder.access_token,
                order: this.selfOrder.currentOrder.serializeForORM(),
                payment_method_id: this.state.paymentMethodId,
                customer: { name: t.name, phone: t.phone, email: t.email },
            });
            t.view = result.transfer;
            t.step = "clabe";
            this.xpagoTransferWatch(result.order[0].id, result.transfer.id);
        } catch (error) {
            this.selfOrder.handleErrorNotification(error);
            this.selfOrder.paymentError = true;
        } finally {
            t.busy = false;
        }
    },

    /** Ask whether the money arrived until it does, the transfer ends, or the kiosk's time runs out. */
    async xpagoTransferWatch(orderId, transferId) {
        this.xpagoTransferStop(false);
        const run = { orderId, transferId, active: true, startedAt: Date.now() };
        this.xpagoTransferRun = run;
        this.xpagoTransfer.now = Date.now();
        const seconds = this.selfOrder.config.xpago_kiosk_transfer_timeout;
        if (seconds > 0) {
            run.timer = setTimeout(async () => {
                if (!run.active) {
                    return;
                }
                await this.xpagoTransferStop(true);
                this.selfOrder.notification.add(
                    _t("The transfer did not arrive in time and the CLABE was cancelled. Do not send money to it."),
                    { type: "warning" }
                );
                this.xpagoTransferBack();
            }, seconds * 1000);
        }
        while (run.active) {
            await new Promise((resolve) => setTimeout(resolve, transferDelay(Date.now() - run.startedAt)));
            if (!run.active) {
                return;
            }
            let view;
            try {
                view = await rpc("/pos-self-order/xpago-transfer-status/", {
                    access_token: this.selfOrder.access_token,
                    order_id: orderId,
                    transfer_id: transferId,
                });
            } catch {
                continue; // a lost connection: ask again
            }
            if (!run.active) {
                return;
            }
            this.xpagoTransfer.view = view;
            if (TRANSFER_FINAL_STATES.includes(view.state) || view.state === "expired") {
                run.active = false;
                clearTimeout(run.timer);
                if (view.state !== "paid") {
                    // The order then waits on the server: the customer chooses again.
                    this.selfOrder.notification.add(_t("The CLABE is no longer valid. Do not send money to it."), {
                        type: "warning",
                    });
                    this.xpagoTransferBack();
                }
                // Paid: the server already paid the order and tells the kiosk, which shows the confirmation.
            }
        }
    },

    async xpagoTransferStop(cancel) {
        const run = this.xpagoTransferRun;
        if (!run?.active) {
            return;
        }
        run.active = false;
        clearTimeout(run.timer);
        if (cancel) {
            await rpc("/pos-self-order/xpago-transfer-cancel/", {
                access_token: this.selfOrder.access_token,
                order_id: run.orderId,
                transfer_id: run.transferId,
            }).catch(() => {});
        }
    },

    /** «Cancel» on the kiosk: the CLABE stops taking money and the customer picks how to pay again. */
    async xpagoTransferCancel() {
        await this.xpagoTransferStop(true);
        this.xpagoTransferBack();
    },

    xpagoTransferBack() {
        this.xpagoTransfer.step = null;
        this.xpagoTransfer.view = null;
        if (this.selfOrder.models["pos.payment.method"].length > 1) {
            this.state.selection = true;
            this.state.paymentMethodId = null;
        } else {
            this.back();
        }
    },
});
