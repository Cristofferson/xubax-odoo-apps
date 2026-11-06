/** How often the point of sale and the kiosk ask Odoo how a terminal charge is going: often at first (most cards
 *  are paid in seconds), less and less after, and once more right when the charge expires. The server's scheduled
 *  action stays the safety net for a screen that closed. Shared by the register and the kiosk. */

export const FINAL_STATES = ["confirmed", "cancelled", "expired", "refunded"];

const STEPS = [
    [20000, 2000], // the first 20 s: every 2 s
    [60000, 5000], // up to a minute: every 5 s
];
const SLOW_DELAY = 10000;

function parseServerDatetime(value) {
    return value ? Date.parse(value.replace(" ", "T") + "Z") : NaN;
}

/** Milliseconds to wait before asking again, `elapsed` ms after the charge was sent. */
export function nextDelay(elapsed, expiresAt, now = Date.now()) {
    let delay = SLOW_DELAY;
    for (const [until, every] of STEPS) {
        if (elapsed < until) {
            delay = every;
            break;
        }
    }
    const untilExpiry = parseServerDatetime(expiresAt) - now + 1000;
    if (untilExpiry > 0 && untilExpiry < delay) {
        delay = untilExpiry;
    }
    return delay;
}

/** Ask with `refresh(charge)` until the charge ends or `isActive()` turns false (the screen was left). Resolves with
 *  the last charge read; a lost connection is not an answer, so it keeps asking. */
export async function waitForCharge(charge, refresh, isActive = () => true) {
    const start = Date.now();
    while (!FINAL_STATES.includes(charge.state) && isActive()) {
        await new Promise((resolve) => setTimeout(resolve, nextDelay(Date.now() - start, charge.expires_at)));
        if (!isActive()) {
            break;
        }
        try {
            charge = await refresh(charge);
        } catch {
            // Offline or Odoo unreachable: keep asking; the cashier can still cancel.
        }
    }
    return charge;
}
