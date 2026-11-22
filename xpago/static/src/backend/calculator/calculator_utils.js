/** The arithmetic of the calculator, kept apart so it can be tested on its own. */

export const OPERATORS = ["+", "-", "×", "÷"];

/** Rounds away the binary noise of floats (0.1 + 0.2 = 0.3). */
export function clean(value) {
    return Number(Number(value).toPrecision(12));
}

/** [number, operator, number, ...] → the result, × and ÷ before + and −; null when dividing by zero. */
export function evaluate(tokens) {
    const items = tokens.filter((t, i) => i % 2 === 1 || t !== "");
    if (!items.length) {
        return 0;
    }
    if (OPERATORS.includes(items[items.length - 1])) {
        items.pop();
    }
    const sums = [Number(items[0])];
    const signs = [];
    for (let i = 1; i < items.length; i += 2) {
        const op = items[i];
        const value = Number(items[i + 1]);
        if (op === "×") {
            sums[sums.length - 1] *= value;
        } else if (op === "÷") {
            if (value === 0) {
                return null;
            }
            sums[sums.length - 1] /= value;
        } else {
            signs.push(op);
            sums.push(value);
        }
    }
    let total = sums[0];
    signs.forEach((sign, i) => (total = sign === "+" ? total + sums[i + 1] : total - sums[i + 1]));
    return clean(total);
}

/** «%» on the number being typed: 200 + 15% adds 15% of 200 (as shop calculators do); 80 × 15% is 80 × 0.15. */
export function percent(tokens, entry) {
    const value = Number(entry || 0);
    const op = tokens[tokens.length - 1];
    if (op === "+" || op === "-") {
        return clean((evaluate(tokens.slice(0, -1)) * value) / 100);
    }
    return clean(value / 100);
}

/** A typed number for the screen: thousands grouped, the decimals as typed. */
export function formatEntry(entry, { decimalPoint = ".", thousandsSep = "," } = {}) {
    const text = String(entry ?? "");
    const negative = text.startsWith("-");
    const [whole, decimals] = (negative ? text.slice(1) : text).split(".");
    const grouped = (whole || "0").replace(/\B(?=(\d{3})+(?!\d))/g, thousandsSep);
    return (negative ? "-" : "") + grouped + (decimals !== undefined ? decimalPoint + decimals : "");
}

/** A result as text the user can keep typing on: no exponent, at most 10 decimals. */
export function toEntry(value) {
    if (!Number.isFinite(value)) {
        return "0";
    }
    return String(Number(value.toFixed(10)));
}

/** The amount to charge: the result rounded to the currency, only when positive. */
export function chargeAmount(value, digits = 2) {
    const amount = Number(Number(value || 0).toFixed(digits));
    return amount > 0 ? amount : 0;
}

/** Money as the company shows it. */
export function formatMoney(amount, { symbol = "$", position = "before", digits = 2 } = {}, separators = {}) {
    const text = formatEntry(Number(amount || 0).toFixed(digits), separators);
    return position === "after" ? `${text} ${symbol}` : `${symbol} ${text}`;
}

/** The serial number the XPago terminal app tells this page ("" outside a terminal or when it does not know). */
export function deviceSerial(device = window.XPagoDevice) {
    try {
        return (device?.serial?.() || "").trim();
    } catch {
        return "";
    }
}

/** The terminal of the list with this serial (the app may know it with or without its prefix). */
export function terminalOfSerial(terminals, serial) {
    if (!serial) {
        return undefined;
    }
    return terminals.find((t) => t.serial && (serial.endsWith(t.serial) || t.serial.endsWith(serial)));
}
