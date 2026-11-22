/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { Component, onWillStart, onWillUnmount, useExternalListener, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { localization } from "@web/core/l10n/localization";
import { browser } from "@web/core/browser/browser";
import {
    OPERATORS,
    chargeAmount,
    deviceSerial,
    evaluate,
    formatEntry,
    formatMoney,
    percent,
    terminalOfSerial,
    toEntry,
} from "@xpago/backend/calculator/calculator_utils";

const TERMINAL_KEY = "xpago_calculator.terminal";
const DEVICE_KEY = "xpago_calculator.this_terminal";
const FINAL = ["confirmed", "cancelled", "expired", "refunded"];

/** Big-key calculator; when the company allows it, «Charge» sends the result to an XPago terminal. */
export class XpagoCalculator extends Component {
    static template = "xpago.Calculator";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            tokens: [], // [number, operator, number, operator ...] already entered
            entry: "", // the number being typed
            done: false, // «=» was pressed: a digit starts a new calculation
            error: false,
            info: { charge: false, terminals: [], currency: {} },
            terminalId: false,
            onDevice: false, // running in an XPago terminal: it charges on itself, no list
            askDevice: false, // in a terminal that does not know its serial: «Which terminal is this?» once
            charge: null, // {phase: waiting|paid|failed, amount, message, card}
        });
        this.separators = { decimalPoint: localization.decimalPoint, thousandsSep: localization.thousandsSep };
        this.stopped = false;
        onWillStart(async () => {
            this.state.info = await this.orm.call("pos.payment.method", "xpago_calculator_info", []);
            const terminals = this.state.info.terminals;
            if (window.XPagoDevice) {
                const mine = terminalOfSerial(terminals, deviceSerial())
                    || terminals.find((t) => t.id === Number(browser.localStorage.getItem(DEVICE_KEY)));
                if (mine) {
                    Object.assign(this.state, { terminalId: mine.id, onDevice: true });
                    return;
                }
                this.state.askDevice = terminals.length > 1;
            }
            const saved = Number(browser.localStorage.getItem(TERMINAL_KEY));
            this.state.terminalId = (terminals.find((t) => t.id === saved) || terminals[0])?.id || false;
        });
        onWillUnmount(() => {
            this.stopped = true;
        });
        useExternalListener(window, "keydown", (ev) => this.onKeydown(ev));
        this.keys = [
            ["C", "⌫", "%", "÷"],
            ["7", "8", "9", "×"],
            ["4", "5", "6", "-"],
            ["1", "2", "3", "+"],
            ["00", "0", ".", "="],
        ];
    }

    // === SCREEN === //

    get expression() {
        const parts = this.state.tokens.map((t, i) => (i % 2 ? ` ${t === "-" ? "−" : t} ` : formatEntry(t, this.separators)));
        return parts.join("");
    }

    get result() {
        const tokens = this.state.entry !== "" ? [...this.state.tokens, this.state.entry] : this.state.tokens;
        return evaluate(tokens);
    }

    get display() {
        if (this.state.error) {
            return _t("Cannot divide by 0");
        }
        if (this.state.entry !== "") {
            return formatEntry(this.state.entry, this.separators);
        }
        const value = this.result;
        return formatEntry(toEntry(value ?? 0), this.separators);
    }

    get amount() {
        const value = this.result;
        return value === null ? 0 : chargeAmount(value, this.state.info.currency.digits ?? 2);
    }

    money(amount) {
        return formatMoney(amount, this.state.info.currency, this.separators);
    }

    keyLabel(key) {
        return { "-": "−", ".": localization.decimalPoint }[key] || key;
    }

    keyClass(key) {
        if (key === "=") {
            return "o_xpago_calc_equal";
        }
        if (OPERATORS.includes(key) || key === "%") {
            return "o_xpago_calc_op";
        }
        return ["C", "⌫"].includes(key) ? "o_xpago_calc_clear" : "o_xpago_calc_digit";
    }

    // === KEYS === //

    press(key) {
        const state = this.state;
        if (key === "C") {
            Object.assign(state, { tokens: [], entry: "", done: false, error: false });
            return;
        }
        if (state.error) {
            Object.assign(state, { tokens: [], entry: "", error: false });
        }
        if (/^\d+$/.test(key) || key === ".") {
            if (state.done) {
                Object.assign(state, { tokens: [], entry: "", done: false });
            }
            if (key === "." && state.entry.includes(".")) {
                return;
            }
            const next = key === "." && !state.entry ? "0." : state.entry + key;
            state.entry = /^0\d/.test(next) ? next.replace(/^0+(?=\d)/, "") || "0" : next;
            return;
        }
        state.done = false;
        if (key === "⌫") {
            state.entry = state.entry.slice(0, -1);
            if (!state.entry && state.tokens.length) {
                const last = state.tokens.pop();
                if (!OPERATORS.includes(last)) {
                    state.entry = last;
                }
            }
            return;
        }
        if (key === "%") {
            state.entry = toEntry(percent(state.tokens, state.entry || "0"));
            return;
        }
        if (OPERATORS.includes(key)) {
            if (state.entry === "" && !state.tokens.length) {
                state.tokens = ["0", key];
            } else if (state.entry === "") {
                state.tokens[state.tokens.length - 1] = key; // change of mind: the last operator is replaced
            } else {
                state.tokens.push(state.entry, key);
                state.entry = "";
            }
            return;
        }
        if (key === "=") {
            const value = this.result;
            if (value === null) {
                state.error = true;
                return;
            }
            Object.assign(state, { tokens: [], entry: toEntry(value), done: true });
        }
    }

    onKeydown(ev) {
        if (this.state.charge) {
            return;
        }
        const map = { "*": "×", "/": "÷", Enter: "=", Backspace: "⌫", Escape: "C", ",": "." };
        const key = map[ev.key] || ev.key;
        if (/^\d$/.test(key) || [".", "+", "-", "×", "÷", "%", "=", "⌫", "C"].includes(key)) {
            ev.preventDefault();
            this.press(key);
        }
    }

    // === CHARGE === //

    get terminal() {
        return this.state.info.terminals.find((t) => t.id === this.state.terminalId);
    }

    chooseTerminal(ev) {
        this.state.terminalId = Number(ev.target.value);
        browser.localStorage.setItem(TERMINAL_KEY, String(this.state.terminalId));
    }

    /** In a terminal: «this is terminal X», remembered on this device; the list does not show again. */
    chooseThisTerminal(ev) {
        const id = Number(ev.target.value);
        if (!id) {
            return;
        }
        browser.localStorage.setItem(DEVICE_KEY, String(id));
        Object.assign(this.state, { terminalId: id, onDevice: true, askDevice: false });
    }

    _call(method, args) {
        return this.orm.silent.call("pos.payment.method", method, [[this.terminal.id], ...args]);
    }

    async charge() {
        const amount = this.amount;
        const terminal = this.terminal;
        if (!amount || !terminal || this.state.charge) {
            return;
        }
        this.state.charge = { phase: "waiting", amount, terminal: terminal.name, message: "" };
        let charge;
        try {
            charge = await this._call("xpago_create_charge", [
                { amount, session_id: false, order_uuid: `calc-${Date.now().toString(36)}` },
            ]);
        } catch (error) {
            this._fail(error.data?.message || error.message || String(error));
            return;
        }
        this.state.charge.id = charge.id;
        if (terminal.open_app && charge.terminal_app_url) {
            this._openTerminalApp(charge.terminal_app_url);
        }
        const result = await this._wait(charge, terminal);
        if (!this.state.charge) {
            return;
        }
        if (result.state === "confirmed") {
            const pay = result.payment || {};
            this.state.charge.phase = "paid";
            this.state.charge.card = [pay.card_brand || pay.card_type, pay.card_no && `•••• ${pay.card_no}`]
                .filter(Boolean)
                .join(" ");
            this.state.charge.auth = pay.payment_method_authcode || "";
            this.state.charge.amount = result.charged_amount || amount;
        } else if (result.timed_out) {
            this._fail(_t("The card was not presented in time: the charge was cancelled on the terminal."));
        } else if (result.state === "expired") {
            this._fail(_t("The charge expired on the terminal before it was paid."));
        } else if (!this.state.charge.cancelling) {
            this._fail(_t("The charge was not paid."));
        } else {
            this.state.charge = null;
        }
    }

    async _wait(charge, terminal) {
        const deadline = terminal.timeout > 0 ? Date.now() + terminal.timeout * 1000 : 0;
        let current = charge;
        while (!FINAL.includes(current.state) && !this.stopped && this.state.charge) {
            await new Promise((resolve) => setTimeout(resolve, 2000));
            try {
                current = deadline && Date.now() >= deadline
                    ? await this._call("xpago_timeout_charge", [charge.id])
                    : await this._call("xpago_charge_status", [charge.id]);
            } catch {
                // No connection for a moment: keep asking.
            }
        }
        return current;
    }

    async cancelCharge() {
        const charge = this.state.charge;
        if (!charge?.id) {
            return;
        }
        charge.cancelling = true;
        try {
            const view = await this._call("xpago_cancel_charge", [charge.id]);
            if (view.state === "confirmed") {
                charge.cancelling = false; // paid just before: the waiting loop shows it
            }
        } catch (error) {
            charge.cancelling = false;
            this.notification.add(error.data?.message || error.message || String(error), { type: "danger" });
        }
    }

    _fail(message) {
        Object.assign(this.state.charge, { phase: "failed", message });
    }

    closeCharge() {
        const paid = this.state.charge?.phase === "paid";
        this.state.charge = null;
        if (paid) {
            Object.assign(this.state, { tokens: [], entry: "", done: false, error: false });
        }
    }

    _openTerminalApp(url) {
        // The charge app of the terminal takes the charge when Odoo runs on the same device.
        const iframe = document.createElement("iframe");
        iframe.style.display = "none";
        iframe.src = url;
        document.body.appendChild(iframe);
        setTimeout(() => iframe.remove(), 1000);
    }
}

registry.category("actions").add("xpago_calculator", XpagoCalculator);
