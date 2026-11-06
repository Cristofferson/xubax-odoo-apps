/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { PosStore, register_payment_method } from "@point_of_sale/app/store/pos_store";
import { Payment } from "@point_of_sale/app/store/models";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";

import { waitForCharge } from "@xpago_pos/app/charge_wait";

/** The confirmation of a split charge: one line per part. */
export class XpagoSplitPopup extends ConfirmPopup {
    static template = "xpago_pos.XpagoSplitPopup";
}

patch(PosStore.prototype, {
    async _processData(loadedData) {
        await super._processData(...arguments);
        this.xpago_bank_accounts = loadedData["payment.xpago.bank.account"] || [];
    },
});

export class PaymentXpago extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.charges = {}; // payment line cid -> {id}
    }

    _call(method, args) {
        return this.env.services.orm.silent.call("pos.payment.method", method, [
            [this.payment_method.id],
            ...args,
        ]);
    }

    async send_payment_request(cid) {
        await super.send_payment_request(...arguments);
        const order = this.pos.get_order();
        const line = order.get_paymentline(cid);
        if (line.amount < 0) {
            return this._refund(order, line);
        }
        if (line.amount === 0) {
            this._showError(_t("XPago terminals only charge positive amounts."));
            return false;
        }
        // The XPago payment rules decide the account (and the months, only shown here: the terminal does not take
        // them) of this charge, or split it in parts.
        if (!line.xpagoPart) {
            const parts = await this._plan(order, line);
            if (!parts) {
                return false;
            }
        }
        const part = line.xpagoPart || {};
        const accountId = await this._chooseAccount(part);
        if (accountId === false) {
            return false;
        }
        if (!accountId && this.pos.config.xpago_show_account && part.account_name) {
            this.env.services.pos_notification.add(
                [_t("Deposit: %s", part.account_name), this._termsText(part.terms)].filter(Boolean).join(" · "),
                4000
            );
        }
        line.set_payment_status("waitingCapture");
        let charge;
        try {
            charge = await this._call("xpago_create_charge", [
                {
                    amount: line.amount,
                    session_id: this.pos.pos_session?.id,
                    order_uuid: order.uid,
                    bank_account_id: accountId,
                    rule_account_id: part.account_id || false,
                },
            ]);
        } catch (error) {
            this._showError(error.data?.message || error.message || String(error));
            return false;
        }
        this.charges[cid] = { id: charge.id, stopped: false };
        line.set_payment_status("waitingCard");
        if (this.payment_method.xpago_open_terminal_app && charge.terminal_app_url) {
            this._openTerminalApp(charge.terminal_app_url);
        }
        const result = await this._waitForResult(cid, charge, order);
        delete this.charges[cid];
        if (result.state === "confirmed") {
            const { ticket, ...payment } = result.payment;
            Object.assign(line, payment);
            if (ticket) {
                line.set_receipt_info(ticket);
            }
            // Next part of a split sale: selected, so the cashier only presses Send.
            const next = order
                .get_paymentlines()
                .find((p) => p.xpagoPart && p !== line && p.get_payment_status() === "pending");
            if (next) {
                order.select_paymentline(next);
            }
            return true;
        }
        if (result.state === "expired") {
            this._showError(_t("The charge expired on the terminal before it was paid."));
        }
        return false;
    }

    _termsText(terms) {
        if (!terms) {
            return "";
        }
        const months = terms.filter((t) => t > 1);
        return months.length ? _t("Months without interest: %s", months.join(", ")) : _t("Single payment");
    }

    /** Ask Odoo how this payment is charged. With several parts (different accounts or months), the cashier
     *  confirms and the payment line becomes one line per part, each sent to the terminal on its own. */
    async _plan(order, line) {
        let plan;
        try {
            plan = await this._call("xpago_plan", [
                {
                    session_id: this.pos.pos_session?.id,
                    total: order.get_total_with_tax(),
                    amount: line.amount,
                    lines: order.get_orderlines().map((l) => ({
                        product_id: l.product?.id,
                        qty: l.get_quantity(),
                        amount: l.get_price_with_tax(),
                    })),
                },
            ]);
        } catch {
            line.xpagoPart = {};
            return []; // the rules must never stop a charge
        }
        const parts = plan.parts || [];
        if (parts.length <= 1) {
            line.xpagoPart = parts[0] || {};
            return parts;
        }
        const money = (value) => this.env.utils.formatCurrency(value);
        const summary = parts
            .map(
                (p, i) =>
                    `${i + 1}. ${money(p.amount)}` +
                    (plan.show_account && p.account_name ? ` → ${p.account_name}` : "") +
                    (this._termsText(p.terms) ? ` (${this._termsText(p.terms)})` : "")
            )
            .join("\n");
        const intro = _t(
            "Its products go to different accounts or allow different months, so the customer pays each part with the card:"
        );
        const { confirmed } = await this.env.services.popup.add(XpagoSplitPopup, {
            title: _t("This sale is charged in %s parts", parts.length),
            body: `${intro}\n\n${summary}`,
            confirmText: _t("Charge the first part"),
            cancelText: _t("Cancel"),
        });
        if (!confirmed) {
            return null;
        }
        line.set_amount(parts[0].amount);
        line.xpagoPart = parts[0];
        for (const part of parts.slice(1)) {
            // Not order.add_paymentline: it refuses while this line waits for the terminal.
            const extra = new Payment(
                { env: order.env },
                { order, payment_method: this.payment_method, pos: this.pos }
            );
            order.paymentlines.add(extra);
            extra.set_amount(part.amount);
            extra.set_payment_status("pending");
            extra.xpagoPart = part;
        }
        return parts;
    }

    async _chooseAccount(part = {}) {
        // When this terminal lets the cashier choose, ask for the deposit account before charging; the account of
        // the payment rules, else the terminal's, comes selected.
        const method = this.payment_method;
        const accounts = this.pos.xpago_bank_accounts || [];
        if (!method.xpago_choose_account || accounts.length < 2) {
            return null;
        }
        const preset = part.account_id || (method.xpago_bank_account_id && method.xpago_bank_account_id[0]);
        const { confirmed, payload } = await this.env.services.popup.add(SelectionPopup, {
            title: _t("Deposit account"),
            list: accounts.map((account) => ({
                id: account.id,
                label: account.name,
                isSelected: account.id === preset,
                item: account.id,
            })),
        });
        return (confirmed && payload) || false;
    }

    async _waitForResult(cid, charge, order) {
        // Stop asking once the payment line is gone (removed, or the order was left) or the point of sale closes.
        const active = () => Boolean(this.charges[cid] && !this.charges[cid].stopped && order.get_paymentline(cid));
        return waitForCharge(charge, (current) => this._call("xpago_charge_status", [current.id]), active);
    }

    close() {
        for (const pending of Object.values(this.charges)) {
            pending.stopped = true;
        }
        return super.close(...arguments);
    }

    async send_payment_cancel(order, cid) {
        await super.send_payment_cancel(...arguments);
        const pending = this.charges[cid];
        if (!pending) {
            return true;
        }
        try {
            const charge = await this._call("xpago_cancel_charge", [pending.id]);
            // A card approved before the cancel arrived stays paid: the waiting loop keeps it.
            return charge.state !== "confirmed";
        } catch (error) {
            this._showError(error.data?.message || error.message || String(error));
            return false;
        }
    }

    /** A refund order paid back with this method: XPago gives the whole card payment of the original sale back to
     *  the same card, the same day. */
    async _refund(order, line) {
        const refundedOrderIds = [
            ...new Set(
                order
                    .get_orderlines()
                    .map((l) => this.pos.toRefundLines[l.refunded_orderline_id]?.orderline.orderBackendId)
                    .filter(Boolean)
            ),
        ];
        line.set_payment_status("waitingCard");
        try {
            const result = await this._call("xpago_refund_charge", [
                { amount: line.amount, refunded_order_ids: refundedOrderIds },
            ]);
            const { ticket, ...payment } = result.payment || {};
            Object.assign(line, payment);
            if (ticket) {
                line.set_receipt_info(ticket);
            }
            return true;
        } catch (error) {
            this._showError(error.data?.message || error.message || String(error));
            return false;
        }
    }

    _openTerminalApp(url) {
        // The charge app of the terminal takes the charge when the point of sale runs on the same device.
        const iframe = document.createElement("iframe");
        iframe.style.display = "none";
        iframe.src = url;
        document.body.appendChild(iframe);
        setTimeout(() => iframe.remove(), 1000);
    }

    _showError(message) {
        this.env.services.popup.add(ErrorPopup, { title: _t("XPago"), body: message });
    }
}

register_payment_method("xpago", PaymentXpago);
