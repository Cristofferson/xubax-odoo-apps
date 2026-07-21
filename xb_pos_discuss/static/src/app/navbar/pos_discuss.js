/** @odoo-module **/

import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { browser } from "@web/core/browser/browser";
import { onWillUnmount, useState } from "@odoo/owl";

// While the panel is open Discuss keeps itself live through the bus, so the
// badge only has to stay fresh while it is closed: one small query every 15 s
// per terminal is plenty.
const UNREAD_POLL_MS = 15000;

patch(Navbar.prototype, {
    setup() {
        super.setup(...arguments);
        this.xbDiscuss = useState({
            unread: 0,
            open: false,
            // The iframe is created on the first open and then kept alive, so
            // reopening the panel is instant and the conversation is preserved.
            mounted: false,
        });
        this.xbDiscussTimer = null;
        if (this.xbDiscussEnabled) {
            this.xbFetchUnread();
            this.xbDiscussTimer = browser.setInterval(
                () => this.xbFetchUnread(),
                UNREAD_POLL_MS
            );
        }
        onWillUnmount(() => {
            if (this.xbDiscussTimer) {
                browser.clearInterval(this.xbDiscussTimer);
            }
        });
    },

    get xbDiscussEnabled() {
        return Boolean(this.pos?.config?.xb_discuss_enabled);
    },

    async xbFetchUnread() {
        if (this.xbDiscuss.open) {
            // Discuss is on screen and marking channels as read: polling now
            // would only show counts that are about to drop to zero.
            return;
        }
        try {
            const { count } = await rpc("/xb_pos_discuss/unread");
            this.xbDiscuss.unread = count || 0;
        } catch {
            // A POS is expected to run through network hiccups: keep the last
            // known badge instead of flooding the console.
        }
    },

    xbToggleDiscuss() {
        this.xbDiscuss.open = !this.xbDiscuss.open;
        if (this.xbDiscuss.open) {
            this.xbDiscuss.mounted = true;
        } else {
            this.xbFetchUnread();
        }
    },

    onXbDiscussLoaded(ev) {
        // Same-origin iframe, so its document can be styled from here: hide the
        // back-office top bar to leave Discuss alone in the panel — cashiers get
        // their messages, not a door into the back office.
        try {
            const doc = ev.target.contentDocument;
            if (!doc) {
                return;
            }
            const style = doc.createElement("style");
            style.textContent = `
                .o_main_navbar { display: none !important; }
                .o_action_manager, .o_web_client { height: 100% !important; }
            `;
            doc.head.appendChild(style);
        } catch {
            // If a browser ever refuses the access, the panel simply keeps the
            // back-office bar and Discuss still works.
        }
    },
});
