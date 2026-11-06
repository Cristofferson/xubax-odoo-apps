import { describe, expect, test } from "@odoo/hoot";
import { nextDelay } from "@xpago_pos/app/charge_wait";

describe("XPago: waiting for a terminal charge", () => {
    test("asks often at first, then less", () => {
        expect(nextDelay(0, false)).toBe(2000);
        expect(nextDelay(19000, false)).toBe(2000);
        expect(nextDelay(30000, false)).toBe(5000);
        expect(nextDelay(90000, false)).toBe(10000);
    });

    test("asks once more right when the charge expires", () => {
        const now = Date.parse("2026-11-06T10:00:00Z");
        expect(nextDelay(90000, "2026-11-06 10:00:03", now)).toBe(4000);
        expect(nextDelay(90000, "2026-11-06 09:59:00", now)).toBe(10000);
    });
});
