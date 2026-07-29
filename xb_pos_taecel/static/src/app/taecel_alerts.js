/** Tells the cashier when a recharge came back rejected.
 *
 *  A recharge is dispatched after the ticket closes, never during it: TAECEL is
 *  allowed up to 60 seconds to answer and no counter can hold a customer that
 *  long. The price of that is a verdict arriving when the screen has already
 *  moved on to the next sale -- so the register asks for it. Every few seconds
 *  it polls the outcomes of its own session and, for anything the cashier has
 *  to act on, raises a popup: the customer paid for a recharge that never
 *  arrived and is very likely still standing there.
 *
 *  Polling rather than the bus on purpose: the two supported series expose
 *  different bus plumbing to the POS, and this one cheap indexed query keeps
 *  the module identical on both. It is also what makes the warning survive a
 *  browser reload -- the server, not the tab, remembers what has been seen.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PosStore } from "./compat";

/** How often the register asks for verdicts. Dispatch itself takes seconds,
 *  so this is what the cashier actually waits, and the query is one indexed
 *  read per open register. */
const POLL_MS = 5000;

patch(PosStore.prototype, {
    async setup(...args) {
        await super.setup(...args);
        this.xbTaecelWatchOutcomes();
    },

    xbTaecelWatchOutcomes() {
        if (this._xbTaecelTimer) {
            return;
        }
        this._xbTaecelPending = new Set();
        this._xbTaecelTimer = setInterval(() => this.xbTaecelPollOutcomes(), POLL_MS);
    },

    async xbTaecelPollOutcomes() {
        // Nothing is loaded before the session data arrives, and a register
        // without a TAECEL account never sells one.
        if (!this.xbTaecelEnabled || this._xbTaecelPolling) {
            return;
        }
        const sessionId = this.session?.id;
        if (!sessionId) {
            return;
        }
        this._xbTaecelPolling = true;
        try {
            const alerts = await this.env.services.orm.call(
                "xb.taecel.transaction",
                "xb_pos_alerts",
                [sessionId]
            );
            for (const alert of alerts) {
                this.xbTaecelShowOutcome(alert);
            }
        } catch {
            // Offline or the server hiccuped: the alert is still unacknowledged
            // server-side, so the next tick will bring it back.
        } finally {
            this._xbTaecelPolling = false;
        }
    },

    /** One popup per outcome, never two for the same one. */
    xbTaecelShowOutcome(alert) {
        if (this._xbTaecelPending.has(alert.id)) {
            return;
        }
        this._xbTaecelPending.add(alert.id);

        const what = [alert.label, alert.reference].filter(Boolean).join(" · ");
        // 'failed' is settled and the money is the customer's again; 'timeout'
        // is an unknown outcome that TAECEL may still resolve, and refunding it
        // could hand back money for a recharge that did arrive.
        const failed = alert.state === "failed";
        const body = failed
            ? _t(
                  "%(what)s was NOT delivered.\n"
                  + "Reason: %(reason)s\n\n"
                  + "The customer paid %(amount)s for it. Refund that line.",
                  {
                      what,
                      reason: alert.error || _t("rejected by the operator"),
                      amount: this.env.utils.formatCurrency(alert.amount || 0),
                  }
              )
            : _t(
                  "%(what)s has not been confirmed yet.\n\n"
                  + "Do NOT refund it and do NOT sell it again: it is still "
                  + "being verified and may go through. It will be settled "
                  + "under Recharges > Transactions.",
                  { what }
              );

        this.dialog.add(
            AlertDialog,
            {
                title: failed ? _t("Recharge failed") : _t("Recharge unconfirmed"),
                body,
                confirmLabel: _t("Understood"),
                confirmClass: failed ? "btn-danger" : "btn-warning",
            },
            {
                onClose: () => {
                    this._xbTaecelPending.delete(alert.id);
                    this.env.services.orm
                        .call("xb.taecel.transaction", "xb_pos_ack_alerts", [[alert.id]])
                        .catch(() => {
                            // Not acknowledged server-side: it will pop again,
                            // which is the right way to fail for money owed.
                        });
                },
            }
        );
    },
});
