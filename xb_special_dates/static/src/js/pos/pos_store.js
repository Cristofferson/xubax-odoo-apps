/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
import { PartnerReminderPopup } from "./partner_reminder_popup";
import { TodayRemindersPopup } from "./today_reminders_popup";
import { CaptureSpecialDatePopup } from "./capture_special_date_popup";

/*
 * Special Dates patches the POS store WITHOUT touching how data is
 * loaded. Everything is fetched via RPC after the POS is initialised.
 *
 * Behaviours:
 *   1. On session open: show a popup listing every customer with a
 *      special date today.
 *   2. While the session stays open, re-show that popup every N hours.
 *   3. When a product whose POS category triggers capture is added to
 *      the order, prompt the cashier to register a special date for
 *      the customer.
 *   4. If a customer is later assigned to an order that has pending
 *      captures, the popups are shown then (one after another).
 *   5. Before paying, any pending captures are surfaced one more time.
 *
 * Capture queue model
 * -------------------
 * Pending captures are kept per order as an ORDERED LIST OF TASKS, where
 * each task is one of:
 *   - {kind:'single', wishTypeIds:[id],  cfgs:[cfg]}   one trigger category
 *   - {kind:'choice', wishTypeIds:[...], cfgs:[...]}   a single product that
 *                                                      matches several trigger
 *                                                      categories -> the cashier
 *                                                      picks which event applies
 * Only ONE popup is ever on screen (re-entry guard). When it closes we
 * drain the next not-yet-shown task, so several events in one ticket are
 * surfaced one after another instead of being silently dropped.
 */

/**
 * Return ISO 'YYYY-MM-DD' string for the next Saturday strictly after
 * today. If today is Saturday, returns Saturday of the following week
 * (today + 7 days).
 */
function nextSaturdayIso() {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const dow = today.getDay(); // 0=Sun ... 6=Sat
    let daysAhead = (6 - dow + 7) % 7;
    if (daysAhead === 0) daysAhead = 7;
    const out = new Date(today);
    out.setDate(today.getDate() + daysAhead);
    const yyyy = out.getFullYear();
    const mm = String(out.getMonth() + 1).padStart(2, "0");
    const dd = String(out.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
}

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);

        // ===== Today welcome popup (existing behaviour) =====
        this._xbTodayTimer = null;
        this._xbInitTodayPopup().catch((err) => {
            console.warn("[xb_special_dates] today init failed:", err);
        });

        // ===== Capture-at-POS config =====
        // Map<pos_category_id, {wish_type_id, wish_type_name, wish_type_icon}>
        this._xbCaptureConfig = new Map();
        // Map<order.uuid, Array<task>> -- pending capture tasks per order.
        this._xbPendingCaptures = new Map();
        // "orderKey:wt:<wishTypeId>"  -- this wish type is settled for the
        // order (confirmed, dismissed, or already present within 90 days).
        this._xbDismissedWishTypes = new Set();
        // "orderKey:task:<taskKey>"   -- this whole task is settled.
        this._xbDismissedTasks = new Set();
        // Map<order.uuid, Set<taskKey>> -- tasks already surfaced in the
        // current chain. Reset on every fresh trigger (partner set, pay) so
        // a "Later"-postponed task is not re-shown instantly, yet still
        // resurfaces on the next trigger.
        this._xbChainShown = new Map();
        // True while a capture popup is on screen. Re-entry guard: no
        // matter which path triggers a capture (product added, partner
        // set, pre-payment drain), only one popup may be open at a time.
        this._xbCaptureDialogOpen = false;
        this._xbLoadCaptureConfig().catch((err) => {
            console.warn("[xb_special_dates] capture config load failed:", err);
        });
    },

    // ------------------------------------------------------------------
    // Today welcome popup (unchanged)
    // ------------------------------------------------------------------
    async _xbInitTodayPopup() {
        await this._xbShowTodayIfAny();
        if (this._xbInterval && this._xbInterval > 0) {
            const ms = this._xbInterval * 60 * 60 * 1000;
            this._xbTodayTimer = setInterval(() => {
                this._xbShowTodayIfAny().catch((err) => {
                    console.warn("[xb_special_dates] periodic show failed:", err);
                });
            }, ms);
        }
    },

    async _xbShowTodayIfAny() {
        let data;
        try {
            data = await this.env.services.orm.call(
                "res.partner",
                "get_today_pos_reminders",
                []
            );
        } catch (err) {
            console.warn("[xb_special_dates] today fetch failed:", err);
            return;
        }
        if (typeof data.interval_hours === "number") {
            this._xbInterval = data.interval_hours;
        }
        if (!data || !data.count) {
            return;
        }
        try {
            this.dialog.add(TodayRemindersPopup, {
                count: data.count,
                items: data.items,
            });
        } catch (err) {
            console.warn("[xb_special_dates] popup open failed:", err);
        }
    },

    // ------------------------------------------------------------------
    // Per-partner celebration popup (unchanged behaviour)
    // ------------------------------------------------------------------
    async setPartnerToCurrentOrder(partner, ...args) {
        const result = await super.setPartnerToCurrentOrder(partner, ...args);
        this._xbCheckPartnerReminders(partner).catch((err) => {
            console.warn("[xb_special_dates] partner check failed:", err);
        });
        // If this order has pending captures from earlier product additions,
        // now is the time to surface them. Fresh trigger -> reset the chain.
        const order = this._xbGetOrder();
        this._xbResetChain(order);
        this._xbDrainPendingCaptures(order).catch((err) => {
            console.warn("[xb_special_dates] drain pending failed:", err);
        });
        return result;
    },

    async _xbCheckPartnerReminders(partner) {
        if (!partner || !partner.id) return;
        let reminders = [];
        try {
            reminders = await this.env.services.orm.call(
                "res.partner",
                "get_pos_reminder_data",
                [[partner.id]]
            );
        } catch (err) {
            console.warn("[xb_special_dates] reminders fetch failed:", err);
            return;
        }
        if (Array.isArray(reminders) && reminders.length > 0) {
            this.dialog.add(PartnerReminderPopup, {
                partnerName: partner.name || "",
                reminders: reminders,
            });
        }
    },

    // ------------------------------------------------------------------
    // Capture-at-POS
    // ------------------------------------------------------------------

    /** Current order, resilient to the get_order/getOrder rename. */
    _xbGetOrder() {
        return this.get_order ? this.get_order() : this.getOrder?.();
    },

    /** Stable key for an order. */
    _xbOrderKey(order) {
        return order ? (order.uuid || order.name || "") : "";
    },

    /** Start a fresh capture chain for the order (clears "shown" memory). */
    _xbResetChain(order) {
        const key = this._xbOrderKey(order);
        if (!key) return;
        this._xbChainShown.set(key, new Set());
    },

    /** Fetch the category -> wish-type mapping once at startup. */
    async _xbLoadCaptureConfig() {
        let rows;
        try {
            rows = await this.env.services.orm.call(
                "xb.wish.reminders",
                "get_pos_capture_config",
                []
            );
        } catch (err) {
            console.warn("[xb_special_dates] capture config rpc failed:", err);
            return;
        }
        if (!Array.isArray(rows)) return;
        for (const row of rows) {
            this._xbCaptureConfig.set(row.pos_category_id, {
                wish_type_id: row.wish_type_id,
                wish_type_name: row.wish_type_name,
                wish_type_icon: row.wish_type_icon || "🎉",
            });
        }
    },

    /**
     * Return ALL captures triggered by the POS categories of the given
     * product, de-duplicated by wish type. A product may belong to several
     * trigger categories; we surface every distinct event so the cashier
     * can pick the right one (instead of silently taking the first).
     * `product` is a product record from the POS data. Returns [] if none.
     */
    _xbCaptureForProduct(product) {
        if (!product) return [];
        if (!this._xbCaptureConfig || this._xbCaptureConfig.size === 0) {
            return [];
        }
        // pos_categ_ids is a product.template field. In Odoo 19 the POS
        // order line's product_id is a product.product variant. Its
        // template proxy only delegates a field to the template when the
        // field is absent from the variant model -- but product.product
        // inherits pos_categ_ids via _inherits, so the field IS present on
        // the variant model yet is NOT loaded with data in the POS (it's in
        // product.template._load_pos_data_fields, not product.product's).
        // The proxy therefore returns the variant's empty value and never
        // reaches the template. Read the template explicitly first, then
        // fall back to the other shapes defensively.
        const sources = [
            product.product_tmpl_id && product.product_tmpl_id.pos_categ_ids,
            product.pos_categ_ids,
            product.pos_categ_id,
        ];
        let catIds = [];
        for (const src of sources) {
            if (!src) continue;
            if (Array.isArray(src)) {
                catIds = src
                    .map((c) => (typeof c === "object" ? c.id : c))
                    .filter(Boolean);
            } else {
                catIds = [typeof src === "object" ? src.id : src];
            }
            if (catIds.length) break;
        }
        const cfgs = [];
        const seen = new Set();
        for (const id of catIds) {
            const cfg = this._xbCaptureConfig.get(id);
            if (cfg && !seen.has(cfg.wish_type_id)) {
                seen.add(cfg.wish_type_id);
                cfgs.push(cfg);
            }
        }
        return cfgs;
    },

    /**
     * Override addLineToOrder so we can detect when a product belonging
     * to one or more trigger categories is added.
     *
     * Odoo 19's signature: addLineToOrder(vals, order, opts)
     * (we just forward all args to super).
     */
    async addLineToOrder(...args) {
        const line = await super.addLineToOrder(...args);
        try {
            // Resolve the product from the returned line if possible.
            const product = line && line.product_id ? line.product_id : null;
            const cfgs = this._xbCaptureForProduct(product);
            if (cfgs.length) {
                const order = this._xbGetOrder();
                this._xbRegisterTask(order, cfgs);
                // If there's a partner already, try to show now. We do NOT
                // reset the chain here: a newly added product surfaces its
                // own capture without re-nagging captures already postponed
                // earlier in the same ticket.
                const partner =
                    order && (order.get_partner?.() || order.partner_id);
                if (partner && partner.id) {
                    this._xbDrainPendingCaptures(order).catch((err) => {
                        console.warn("[xb_special_dates] capture show failed:", err);
                    });
                }
            }
        } catch (err) {
            console.warn("[xb_special_dates] capture detect failed:", err);
        }
        return line;
    },

    /**
     * Queue a capture task for this order. A task groups every wish type a
     * single product matches; a single-match product yields a 'single'
     * task, a multi-match product a 'choice' task. De-duplicated by task
     * key, and skipped if the whole task was already settled.
     */
    _xbRegisterTask(order, cfgs) {
        const key = this._xbOrderKey(order);
        if (!key || !cfgs || !cfgs.length) return;
        const ids = cfgs.map((c) => c.wish_type_id).sort((a, b) => a - b);
        const kind = ids.length > 1 ? "choice" : "single";
        const taskKey = (kind === "choice" ? "c:" : "s:") + ids.join(",");
        if (this._xbDismissedTasks.has(`${key}:task:${taskKey}`)) {
            return;
        }
        let list = this._xbPendingCaptures.get(key);
        if (!list) {
            list = [];
            this._xbPendingCaptures.set(key, list);
        }
        if (list.some((t) => t.key === taskKey)) {
            return;
        }
        list.push({ key: taskKey, kind, wishTypeIds: ids, cfgs: cfgs.slice() });
    },

    /** Remove a task from the order's pending list. */
    _xbClearTask(order, taskKey) {
        const key = this._xbOrderKey(order);
        const list = this._xbPendingCaptures.get(key);
        if (!list) return;
        const idx = list.findIndex((t) => t.key === taskKey);
        if (idx >= 0) list.splice(idx, 1);
        if (!list.length) this._xbPendingCaptures.delete(key);
    },

    /**
     * Surface pending capture tasks for the order, one popup at a time.
     * Shows the first task not yet seen in the current chain; the rest are
     * chained from each popup's onClose. Tasks whose events all already
     * exist (or are dismissed) are skipped silently.
     */
    async _xbDrainPendingCaptures(order = null) {
        order = order || this._xbGetOrder();
        if (!order) return;
        const key = this._xbOrderKey(order);
        if (!key) return;
        const partner = order.get_partner?.() || order.partner_id;
        if (!partner || !partner.id) return;
        // A popup is already up: it will chain to the next task on close.
        if (this._xbCaptureDialogOpen) return;

        let shown = this._xbChainShown.get(key);
        if (!shown) {
            shown = new Set();
            this._xbChainShown.set(key, shown);
        }

        // Loop so that tasks skipped for being already-satisfied don't stall
        // the chain: keep going until one popup actually opens or we run out.
        // eslint-disable-next-line no-constant-condition
        while (true) {
            const list = this._xbPendingCaptures.get(key);
            if (!list || !list.length) return;
            const task = list.find(
                (t) =>
                    !shown.has(t.key) &&
                    !this._xbDismissedTasks.has(`${key}:task:${t.key}`)
            );
            if (!task) return;
            shown.add(task.key);
            const opened = await this._xbShowCaptureTask(order, partner, task);
            if (opened) return; // popup on screen; continues on close
            // else: nothing left to ask for this task -> try the next one
        }
    },

    /**
     * Show the capture popup for a single task. Filters out wish types
     * already settled or already present within 90 days; if none remain the
     * task is silently cleared. Returns true if a popup was opened.
     */
    async _xbShowCaptureTask(order, partner, task) {
        if (!order || !partner || !task) return false;
        const key = this._xbOrderKey(order);
        // Re-entry guard. Claim the slot before any await so two concurrent
        // calls can't both reach dialog.add.
        if (this._xbCaptureDialogOpen) return false;
        this._xbCaptureDialogOpen = true;
        let opened = false;
        try {
            // Build the still-valid choices for this task.
            const choices = [];
            for (const cfg of task.cfgs) {
                if (
                    this._xbDismissedWishTypes.has(
                        `${key}:wt:${cfg.wish_type_id}`
                    )
                ) {
                    continue;
                }
                // Anti-duplicate: skip a type the partner already has within
                // the next 90 days.
                let exists = false;
                try {
                    exists = await this.env.services.orm.call(
                        "xb.wish.reminders",
                        "check_existing_for_capture",
                        [partner.id, cfg.wish_type_id]
                    );
                } catch (err) {
                    console.warn("[xb_special_dates] dupe-check failed:", err);
                    exists = false;
                }
                if (exists) {
                    this._xbDismissedWishTypes.add(
                        `${key}:wt:${cfg.wish_type_id}`
                    );
                    continue;
                }
                choices.push({
                    wishTypeId: cfg.wish_type_id,
                    name: cfg.wish_type_name,
                    icon: cfg.wish_type_icon || "🎉",
                });
            }

            if (!choices.length) {
                // Nothing left to ask for this task.
                this._xbDismissedTasks.add(`${key}:task:${task.key}`);
                this._xbClearTask(order, task.key);
                return false;
            }

            const partnerName = partner.name || partner.display_name || "";
            const orderRef = order.name || order.uuid || "";
            const self = this;

            const onConfirm = async (dateIso, wishTypeId) => {
                // Settle local state BEFORE the RPC: anything that fires
                // while the call is in flight must see this as handled.
                self._xbDismissedTasks.add(`${key}:task:${task.key}`);
                self._xbDismissedWishTypes.add(`${key}:wt:${wishTypeId}`);
                self._xbClearTask(order, task.key);
                let result;
                try {
                    result = await self.env.services.orm.call(
                        "xb.wish.reminders",
                        "create_from_pos",
                        [partner.id, wishTypeId, dateIso, orderRef]
                    );
                } catch (err) {
                    // Roll back so the user can retry or use "Later".
                    self._xbDismissedTasks.delete(`${key}:task:${task.key}`);
                    self._xbDismissedWishTypes.delete(
                        `${key}:wt:${wishTypeId}`
                    );
                    self._xbRegisterTask(order, task.cfgs);
                    throw err;
                }
                if (result && result.error) {
                    self._xbDismissedTasks.delete(`${key}:task:${task.key}`);
                    self._xbDismissedWishTypes.delete(
                        `${key}:wt:${wishTypeId}`
                    );
                    self._xbRegisterTask(order, task.cfgs);
                    throw new Error(result.error);
                }
                if (self.env.services.notification) {
                    const chosen = task.cfgs.find(
                        (c) => c.wish_type_id === wishTypeId
                    );
                    const icon = (chosen && chosen.wish_type_icon) || "🎉";
                    const nm = (chosen && chosen.wish_type_name) || "";
                    self.env.services.notification.add(`${icon} ${nm} saved`, {
                        type: "success",
                    });
                }
            };
            const onLater = () => {
                // Keep the task pending; it's marked shown for this chain and
                // resurfaces on the next fresh trigger (partner set / pay).
            };
            const onDismiss = () => {
                self._xbDismissedTasks.add(`${key}:task:${task.key}`);
                self._xbClearTask(order, task.key);
            };

            this.dialog.add(
                CaptureSpecialDatePopup,
                {
                    partnerName,
                    choices,
                    defaultDate: nextSaturdayIso(),
                    onConfirm,
                    onLater,
                    onDismiss,
                },
                {
                    // Runs on ANY close path (buttons, ESC, closeAll), so the
                    // guard can never be left stuck. Then chain to the next
                    // pending task, if any.
                    onClose: () => {
                        this._xbCaptureDialogOpen = false;
                        this._xbDrainPendingCaptures(order).catch((err) => {
                            console.warn(
                                "[xb_special_dates] chain drain failed:",
                                err
                            );
                        });
                    },
                }
            );
            opened = true;
            return true;
        } finally {
            if (!opened) {
                this._xbCaptureDialogOpen = false;
            }
        }
    },

    /**
     * Before paying: surface any still-pending captures one more time.
     * We hook into pay() (Odoo 19 POS uses this as the validate trigger).
     */
    async pay(...args) {
        try {
            const order = this._xbGetOrder();
            this._xbResetChain(order);
            await this._xbDrainPendingCaptures(order);
        } catch (err) {
            console.warn("[xb_special_dates] pre-pay drain failed:", err);
        }
        return super.pay(...args);
    },
});
