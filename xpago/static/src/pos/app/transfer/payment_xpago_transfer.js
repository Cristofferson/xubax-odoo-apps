import { _t } from "@web/core/l10n/translation";
import { proxy } from "@odoo/owl";
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { XpagoTransferCustomerDialog, XpagoTransferDialog } from "@xpago/pos/app/transfer/transfer_dialogs";
import {
    TRANSFER_FINAL_STATES,
    customerDefaults,
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
        return this.callPaymentMethod(method, [[this.payment_method_id.id], ...args]);
    }

    async sendPaymentRequest(line) {
        await super.sendPaymentRequest(...arguments);
        const order = line.pos_order_id;
        const uuid = line.uuid;
        if (line.amount <= 0) {
            this._showError(
                _t("A transfer only pays positive amounts. Give refunds back another way (cash or a bank transfer from the business).")
            );
            return false;
        }
        const customer = await makeAwaitable(this.env.services.dialog, XpagoTransferCustomerDialog, {
            defaults: customerDefaults(order.getPartner?.() || order.partner_id, this.pos.company),
            amount: line.amount,
        });
        if (!customer) {
            return false;
        }
        line.setPaymentStatus("waitingCard");
        let transfer;
        try {
            transfer = await this._call("xpago_transfer_create", [
                {
                    amount: line.amount,
                    session_id: order.session_id?.id || this.pos.config.current_session_id?.id,
                    order_uuid: order.uuid,
                    customer,
                },
            ]);
        } catch (error) {
            this._showError(error.data?.message || error.message || String(error));
            return false;
        }
        const entry = { view: proxy({ ...transfer }), stopped: false };
        this.transfers[uuid] = entry;
        this._showClabe(uuid, order);
        await this._waitForMoney(uuid, order);
        this._closeScreens(entry);
        delete this.transfers[uuid];
        if (entry.view.state === "paid") {
            Object.assign(line, entry.view.payment);
            this.env.services.notification.add(_t("The transfer arrived: %s", this._money(entry.view.amount)), {
                type: "success",
            });
            return true;
        }
        return false;
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
        await line.cancelPayment();
    }

    /** A slip with the CLABE, for a customer who would rather take it on paper (template xpago.pos_clabe_receipt). */
    async _print(entry, order) {
        const view = entry.view;
        const expires = view.expires_at ? new Date(Date.parse(view.expires_at.replace(" ", "T") + "Z")) : null;
        const printer = this.pos.ticketPrinter;
        try {
            const generator = printer.getGenerator({ models: this.pos.models, order });
            const data = generator.generateCashMoveData({ reason: "", translatedType: "", formattedAmount: "" });
            data.extra_data = {
                ...data.extra_data,
                xpago_amount: this._money(view.amount_due || view.amount),
                xpago_clabe: formatClabe(view.clabe),
                xpago_bank: view.bank || "",
                xpago_beneficiary: view.beneficiary || "",
                xpago_business: view.business || "",
                xpago_concept: view.concept || "",
                xpago_expires: expires ? expires.toLocaleString() : "",
            };
            const iframe = await printer.generateIframe("xpago.pos_clabe_receipt", data);
            await printer.printWithFallback({ iframe, webFallback: true });
        } catch (error) {
            this._showError(error.message || String(error));
        }
    }

    async sendPaymentCancel(line) {
        await super.sendPaymentCancel(...arguments);
        const entry = this.transfers[line.uuid];
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
        return this.pos.formatCurrency(value || 0);
    }

    _showError(message) {
        this.env.services.dialog.add(AlertDialog, { title: _t("XPago"), body: message });
    }
}

registry.category("pos_payment_providers").add("xpago_spei", PaymentXpagoTransfer);
