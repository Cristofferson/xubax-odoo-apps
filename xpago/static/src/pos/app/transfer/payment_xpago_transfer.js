import { _t } from "@web/core/l10n/translation";
import { reactive } from "@odoo/owl";
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { XpagoClabeReceipt, XpagoTransferDialog } from "@xpago/pos/app/transfer/transfer_dialogs";
import { takenPaymentIds } from "@xpago/pos/app/payment_xpago";
import {
    TRANSFER_FINAL_STATES,
    missingCustomerData,
    formatClabe,
    transferDelay,
} from "@xpago/pos/app/transfer/transfer_utils";

/** «XPago transfer»: the register shows a CLABE made for this sale alone; the customer transfers from any bank
 *  (SPEI) and the payment line completes by itself when the money arrives. */
export class PaymentXpagoTransfer extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.transfers = {}; // payment line uuid -> {view, stopped, closeDialog, closeNotice}
    }

    _call(method, args) {
        return this.env.services.orm.silent.call("pos.payment.method", method, [
            [this.payment_method_id.id],
            ...args,
        ]);
    }

    async sendPaymentRequest(uuid) {
        await super.sendPaymentRequest(...arguments);
        const order = this.pos.getOrder();
        const line = order.getPaymentlineByUuid(uuid);
        if (line.amount < 0) {
            return this._refund(order, line);
        }
        if (line.amount === 0) {
            return false;
        }
        const customer = await this._customer(order);
        if (!customer) {
            return false;
        }
        line.setPaymentStatus("waitingCard");
        let transfer;
        try {
            transfer = await this._call("xpago_transfer_create", [
                {
                    amount: line.amount,
                    session_id: this.pos.config.current_session_id?.id,
                    order_uuid: order.uuid,
                    customer,
                    rule_account_id: await this._ruleAccount(order, line),
                    taken_payment_ids: takenPaymentIds(order, line),
                    followed_transfer_ids: Object.entries(this.transfers)
                        .filter(([key]) => key !== uuid)
                        .map(([, other]) => other.view.id),
                },
            ]);
        } catch (error) {
            this._showError(error.data?.message || error.message || String(error));
            return false;
        }
        const entry = { view: reactive({ ...transfer }), stopped: false };
        // «Retry» right after «Cancel»: the wait of the cancelled CLABE may still be sleeping. It is stopped and must
        // not touch the line any more (it used to clear the new wait and put the line back to «Retry»).
        const previous = this.transfers[uuid];
        if (previous && previous !== entry) {
            previous.stopped = true;
            previous.superseded = true;
            this._closeScreens(previous);
        }
        this.transfers[uuid] = entry;
        this._showClabe(uuid, order);
        await this._waitForMoney(uuid, order);
        if (this.transfers[uuid] === entry) {
            delete this.transfers[uuid];
        }
        if (entry.superseded) {
            return null; // another wait follows this line now
        }
        this._closeScreens(entry);
        if (entry.view.state === "paid") {
            Object.assign(line, entry.view.payment);
            this.env.services.notification.add(_t("The transfer arrived: %s", this._money(entry.view.amount)), {
                type: "success",
            });
            return true;
        }
        return false;
    }

    /** A refund order paid back with «Transfer»: XPago gives the whole transfer of the original sale back to who
     *  paid, the same day only. Otherwise the register says to pay it back in cash. */
    async _refund(order, line) {
        const refundedOrderIds = [
            ...new Set(order.lines.map((l) => l.refunded_orderline_id?.order_id?.id).filter(Boolean)),
        ];
        line.setPaymentStatus("waitingCard");
        try {
            const result = await this._call("xpago_transfer_refund", [
                { amount: line.amount, refunded_order_ids: refundedOrderIds },
            ]);
            Object.assign(line, result.payment || {});
            this.env.services.notification.add(_t("XPago gave the transfer back: %s", this._money(-line.amount)), {
                type: "success",
            });
            return true;
        } catch (error) {
            this._showError(error.data?.message || error.message || String(error));
            return false;
        }
    }

    /** Who pays, the native way: the customer of the sale (Odoo's «Customer required» and customer list when
     *  there is none), with their own card opened when the name, email or phone XPago needs is missing. */
    async _customer(order) {
        let partner = order.getPartner();
        if (!partner) {
            const confirmed = await ask(this.env.services.dialog, {
                title: _t("Customer Required"),
                body: _t("Customer is required for %s payment method.", this.payment_method_id.name),
            });
            if (!confirmed) {
                return false;
            }
            partner = await this.pos.selectPartner(order);
            if (!partner) {
                return false;
            }
        }
        let missing = missingCustomerData(partner);
        if (missing.length) {
            const notice = this.env.services.notification.add(
                _t("To make the CLABE, write the customer's %s and save.", missing.join(_t(" and "))),
                { title: _t("Data missing"), type: "warning", sticky: true }
            );
            try {
                partner = (await this.pos.editPartner(partner)) || partner;
            } catch {
                // The card was closed without saving.
            } finally {
                notice();
            }
            missing = missingCustomerData(partner);
            if (missing.length) {
                this._showError(_t("The CLABE was not made: the customer has no %s.", missing.join(_t(" and "))));
                return false;
            }
            if (order.getPartner()?.id === partner.id) {
                order.setPartner(partner);
            }
        }
        return { name: partner.name.trim(), email: partner.email.trim(), phone: partner.phone || partner.mobile };
    }

    /** The deposit account the XPago payment rules give this sale (by its products, amount and invoice). */
    async _ruleAccount(order, line) {
        try {
            const plan = await this._call("xpago_plan", [
                {
                    session_id: this.pos.config.current_session_id?.id,
                    total: order.totalDue,
                    amount: line.amount,
                    to_invoice: Boolean(order.isToInvoice?.()),
                    lines: order.lines.map((l) => ({ product_id: l.product_id?.id, qty: l.qty, amount: l.priceIncl })),
                },
            ]);
            return plan.parts?.[0]?.account_id || false;
        } catch {
            return false; // the rules must never stop a payment
        }
    }

    /** Ask Odoo until the money arrives, the transfer ends, or the line is gone. A lost connection is not an answer. */
    async _waitForMoney(uuid, order) {
        const entry = this.transfers[uuid];
        const start = Date.now();
        const active = () => !entry.stopped && Boolean(order.getPaymentlineByUuid(uuid));
        while (!TRANSFER_FINAL_STATES.includes(entry.view.state) && active()) {
            await new Promise((resolve) => setTimeout(resolve, transferDelay(Date.now() - start)));
            if (!active() || TRANSFER_FINAL_STATES.includes(entry.view.state)) {
                break;
            }
            try {
                Object.assign(entry.view, await this._call("xpago_transfer_status", [entry.view.id]));
            } catch {
                // Offline or Odoo unreachable: keep asking; the cashier can still cancel.
            }
        }
    }

    _showClabe(uuid, order) {
        const entry = this.transfers[uuid];
        if (!entry || entry.closeDialog) {
            return;
        }
        entry.closeNotice?.();
        entry.closeNotice = null;
        entry.closeDialog = this.env.services.dialog.add(
            XpagoTransferDialog,
            {
                entry,
                renew: () => this._renew(entry),
                cancel: () => this._cancelFromScreen(uuid, order),
                hide: () => entry.closeDialog?.(),
                print: () => this._print(entry, order),
                companyPhone: this.pos.company.phone || "",
            },
            {
                // Closing the screen only hides it: the register keeps waiting, and a notice brings it back.
                onClose: () => {
                    entry.closeDialog = null;
                    if (!entry.done && !TRANSFER_FINAL_STATES.includes(entry.view.state) && !entry.stopped) {
                        entry.closeNotice = this.env.services.notification.add(
                            _t("Waiting for the transfer of %s: the sale is paid by itself when it arrives.", this._money(entry.view.amount)),
                            {
                                type: "info",
                                sticky: true,
                                buttons: [{ name: _t("See the CLABE"), onClick: () => this._showClabe(uuid, order) }],
                            }
                        );
                    }
                },
            }
        );
    }

    _closeScreens(entry) {
        entry.done = true;
        entry.closeDialog?.();
        entry.closeNotice?.();
    }

    async _renew(entry) {
        try {
            Object.assign(entry.view, await this._call("xpago_transfer_renew", [entry.view.id]));
        } catch (error) {
            this._showError(error.data?.message || error.message || String(error));
        }
    }

    /** «Cancel the transfer» on the CLABE screen: the same as the payment line's Cancel. */
    async _cancelFromScreen(uuid, order) {
        const line = order.getPaymentlineByUuid(uuid);
        if (!line) {
            return;
        }
        line.setPaymentStatus("waitingCancel");
        const cancelled = await this.sendPaymentCancel(order, uuid);
        line.setPaymentStatus(cancelled ? "retry" : "waitingCard");
    }

    async _print(entry, order) {
        const view = entry.view;
        const expires = view.expires_at ? new Date(Date.parse(view.expires_at.replace(" ", "T") + "Z")) : null;
        try {
            await this.env.services.printer.print(XpagoClabeReceipt, {
                order,
                view: { ...view },
                amountText: this._money(view.amount_due || view.amount),
                clabeText: formatClabe(view.clabe),
                expiresText: expires ? expires.toLocaleString() : "",
            }, { webPrintFallback: true });
        } catch (error) {
            this._showError(error.message || String(error));
        }
    }

    async sendPaymentCancel(order, uuid) {
        await super.sendPaymentCancel(...arguments);
        const entry = this.transfers[uuid];
        if (!entry) {
            return true;
        }
        let view;
        try {
            view = await this._call("xpago_transfer_cancel", [entry.view.id]);
        } catch (error) {
            this._showError(error.data?.message || error.message || String(error));
            return false;
        }
        Object.assign(entry.view, view);
        if (view.state === "paid") {
            // The money arrived before the cancel: the waiting loop completes the line.
            return false;
        }
        entry.stopped = true;
        this._closeScreens(entry);
        return true;
    }

    close() {
        for (const entry of Object.values(this.transfers)) {
            entry.stopped = true;
            this._closeScreens(entry);
        }
        return super.close(...arguments);
    }

    _money(value) {
        return this.env.utils.formatCurrency(value || 0);
    }

    _showError(message) {
        this.env.services.dialog.add(AlertDialog, { title: _t("XPago"), body: message });
    }
}

register_payment_method("xpago_spei", PaymentXpagoTransfer);
