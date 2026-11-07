import { _t } from "@web/core/l10n/translation";
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { waitForCharge } from "@xpago/pos/app/charge_wait";

export class PaymentXpago extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.charges = {}; // payment line uuid -> {id, cancelled}
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
            this.env.services.notification.add(
                [_t("Deposit: %s", part.account_name), this._termsText(part.terms)].filter(Boolean).join(" · "),
                { type: "info" }
            );
        }
        line.setPaymentStatus("waitingCapture");
        let charge;
        try {
            charge = await this._call("xpago_create_charge", [
                {
                    amount: line.amount,
                    session_id: this.pos.config.current_session_id?.id,
                    order_uuid: order.uuid,
                    bank_account_id: accountId,
                    rule_account_id: part.account_id || false,
                },
            ]);
        } catch (error) {
            this._showError(error.data?.message || error.message || String(error));
            return false;
        }
        this.charges[uuid] = { id: charge.id, cancelled: false };
        line.setPaymentStatus("waitingCard");
        if (this.payment_method_id.xpago_open_terminal_app && charge.terminal_app_url) {
            this._openTerminalApp(charge.terminal_app_url);
        }
        const result = await this._waitForResult(uuid, charge, order);
        delete this.charges[uuid];
        if (result.state === "confirmed") {
            Object.assign(line, result.payment);
            // Next part of a split sale: selected, so the cashier only presses Send.
            const next = order.payment_ids.find(
                (p) => p.xpagoPart && p !== line && p.getPaymentStatus() === "pending"
            );
            if (next) {
                order.selectPaymentline(next);
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
                    session_id: this.pos.config.current_session_id?.id,
                    total: order.totalDue,
                    amount: line.amount,
                    lines: order.lines.map((l) => ({
                        product_id: l.product_id?.id,
                        qty: l.qty,
                        amount: l.priceIncl,
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
        // The dialog keeps line breaks (text-prewrap).
        const intro = _t(
            "Its products go to different accounts or allow different months, so the customer pays each part with the card:"
        );
        const ok = await new Promise((resolve) =>
            this.env.services.dialog.add(
                ConfirmationDialog,
                {
                    title: _t("This sale is charged in %s parts", parts.length),
                    body: `${intro}\n\n${summary}`,
                    confirmLabel: _t("Charge the first part"),
                    cancelLabel: _t("Cancel"),
                    confirm: () => resolve(true),
                    cancel: () => resolve(false),
                },
                { onClose: () => resolve(false) }
            )
        );
        if (!ok) {
            return null;
        }
        line.setAmount(parts[0].amount);
        line.xpagoPart = parts[0];
        for (const part of parts.slice(1)) {
            const extra = this.pos.models["pos.payment"].create({
                pos_order_id: order,
                payment_method_id: this.payment_method_id,
            });
            extra.setAmount(part.amount);
            extra.setPaymentStatus("pending");
            extra.xpagoPart = part;
        }
        return parts;
    }

    async _chooseAccount(part = {}) {
        // When this terminal lets the cashier choose, ask for the deposit account before charging; the account of
        // the payment rules, else the terminal's, comes selected.
        const method = this.payment_method_id;
        const accounts = this.pos.models["payment.xpago.bank.account"]?.getAll() || [];
        if (!method.xpago_choose_account || accounts.length < 2) {
            return null;
        }
        const preset = part.account_id || method.xpago_bank_account_id?.id;
        const picked = await makeAwaitable(this.env.services.dialog, SelectionPopup, {
            title: _t("Deposit account"),
            list: accounts.map((account) => ({
                id: account.id,
                label: account.name,
                isSelected: account.id === preset,
                item: account.id,
            })),
        });
        return picked || false;
    }

    async _waitForResult(uuid, charge, order) {
        // Stop asking once the payment line is gone (removed, or the order was left) or the point of sale closes.
        const active = () => Boolean(this.charges[uuid] && !this.charges[uuid].stopped && order.getPaymentlineByUuid(uuid));
        return waitForCharge(charge, (current) => this._call("xpago_charge_status", [current.id]), active);
    }

    close() {
        for (const pending of Object.values(this.charges)) {
            pending.stopped = true;
        }
        return super.close(...arguments);
    }

    async sendPaymentCancel(order, uuid) {
        await super.sendPaymentCancel(...arguments);
        const pending = this.charges[uuid];
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
            ...new Set(order.lines.map((l) => l.refunded_orderline_id?.order_id?.id).filter(Boolean)),
        ];
        line.setPaymentStatus("waitingCard");
        try {
            const result = await this._call("xpago_refund_charge", [
                { amount: line.amount, refunded_order_ids: refundedOrderIds },
            ]);
            Object.assign(line, result.payment || {});
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
        this.env.services.dialog.add(AlertDialog, { title: _t("XPago"), body: message });
    }
}

register_payment_method("xpago", PaymentXpago);
