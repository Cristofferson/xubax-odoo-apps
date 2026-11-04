import { _t } from "@web/core/l10n/translation";
import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { register_payment_method } from "@point_of_sale/app/store/pos_store";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";

const POLL_DELAY = 2000;

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

    async send_payment_request(uuid) {
        await super.send_payment_request(...arguments);
        const order = this.pos.get_order();
        const line = order.get_paymentline_by_uuid(uuid);
        if (line.amount <= 0) {
            this._showError(_t("XPago terminals only charge positive amounts."));
            return false;
        }
        const accountId = await this._chooseAccount();
        if (accountId === false) {
            return false;
        }
        line.set_payment_status("waitingCapture");
        let charge;
        try {
            charge = await this._call("xpago_create_charge", [
                {
                    amount: line.amount,
                    session_id: this.pos.session?.id,
                    order_uuid: order.uuid,
                    bank_account_id: accountId,
                },
            ]);
        } catch (error) {
            this._showError(error.data?.message || error.message || String(error));
            return false;
        }
        this.charges[uuid] = { id: charge.id, cancelled: false };
        line.set_payment_status("waitingCard");
        if (this.payment_method_id.xpago_open_terminal_app && charge.xpago_id) {
            this._openTerminalApp(charge.xpago_id);
        }
        const result = await this._waitForResult(uuid, charge);
        delete this.charges[uuid];
        if (result.state === "confirmed") {
            Object.assign(line, result.payment);
            return true;
        }
        if (result.state === "expired") {
            this._showError(_t("The charge expired on the terminal before it was paid."));
        }
        return false;
    }

    async _chooseAccount() {
        // When this terminal lets the cashier choose, ask for the deposit account before charging.
        const method = this.payment_method_id;
        const accounts = this.pos.models["payment.xpago.bank.account"]?.getAll() || [];
        if (!method.xpago_choose_account || accounts.length < 2) {
            return null;
        }
        const preset = method.xpago_bank_account_id?.id;
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

    async _waitForResult(uuid, charge) {
        while (!["confirmed", "cancelled", "expired"].includes(charge.state)) {
            await new Promise((resolve) => setTimeout(resolve, POLL_DELAY));
            try {
                charge = await this._call("xpago_charge_status", [charge.id]);
            } catch {
                // A lost connection is not an answer: keep asking.
            }
        }
        return charge;
    }

    async send_payment_cancel(order, uuid) {
        await super.send_payment_cancel(...arguments);
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

    _openTerminalApp(xpagoId) {
        // The charge app of the terminal takes the charge when the point of sale runs on the same device.
        const iframe = document.createElement("iframe");
        iframe.style.display = "none";
        iframe.src = `compago-pos-app:///charge/payment-intent/${xpagoId}`;
        document.body.appendChild(iframe);
        setTimeout(() => iframe.remove(), 1000);
    }

    _showError(message) {
        this.env.services.dialog.add(AlertDialog, { title: _t("XPago"), body: message });
    }
}

register_payment_method("xpago", PaymentXpago);
