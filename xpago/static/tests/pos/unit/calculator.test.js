import { describe, expect, test } from "@odoo/hoot";
import {
    chargeAmount,
    deviceSerial,
    evaluate,
    formatEntry,
    formatMoney,
    percent,
    terminalOfSerial,
    toEntry,
} from "@xpago/backend/calculator/calculator_utils";

describe("XPago calculator: arithmetic", () => {
    test("× and ÷ before + and −, without float noise", () => {
        expect(evaluate(["2", "+", "3", "×", "4"])).toBe(14);
        expect(evaluate(["0.1", "+", "0.2"])).toBe(0.3);
        expect(evaluate(["10", "-", "4", "-", "3"])).toBe(3);
        expect(evaluate(["5", "+"])).toBe(5);
        expect(evaluate(["10", "÷", "0"])).toBe(null);
    });

    test("percent as shop calculators do", () => {
        expect(percent(["200", "+"], "15")).toBe(30);
        expect(percent(["80", "×"], "15")).toBe(0.15);
    });

    test("screen and money", () => {
        expect(formatEntry("1234567.5")).toBe("1,234,567.5");
        expect(toEntry(1 / 3)).toBe("0.3333333333");
        expect(chargeAmount(-5)).toBe(0);
        expect(formatMoney(1250, { symbol: "$", position: "before", digits: 2 })).toBe("$ 1,250.00");
    });
});

describe("XPago calculator: inside a terminal", () => {
    test("finds this terminal by its serial, with or without prefix", () => {
        const terminals = [{ id: 1, serial: "NDB400005405" }, { id: 2, serial: "5406" }, { id: 3, serial: "" }];
        expect(terminalOfSerial(terminals, "NDB400005405").id).toBe(1);
        expect(terminalOfSerial(terminals, "NDB400005406").id).toBe(2);
        expect(terminalOfSerial(terminals, "")).toBe(undefined);
        expect(terminalOfSerial(terminals, "XYZ")).toBe(undefined);
    });

    test("serial told by the terminal app, empty elsewhere", () => {
        expect(deviceSerial({ serial: () => " NDB400005405 " })).toBe("NDB400005405");
        expect(deviceSerial(undefined)).toBe("");
        expect(deviceSerial({ serial: () => { throw new Error("no"); } })).toBe("");
    });
});
