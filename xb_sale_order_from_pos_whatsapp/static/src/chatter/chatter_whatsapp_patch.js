/** @odoo-module **/
// XUBAX - Sales, Quotations & Layaway from POS - WhatsApp add-on
// One WhatsApp button per order: the chatter's own button opens the notices window
// (ready, balance due, late...) instead of the plain template picker, which would also
// offer the notices without the values they need. Every other model is left alone.
import { Chatter } from "@mail/chatter/web_portal/chatter";
import { patch } from "@web/core/utils/patch";

patch(Chatter.prototype, {
    async sendWhatsapp() {
        if (this.props.threadModel !== "sale.order" || !this.state.thread?.id) {
            return super.sendWhatsapp(...arguments);
        }
        const thread = this.state.thread;
        const action = await this.env.services.orm.call(
            "sale.order",
            "action_xb_whatsapp_from_chatter",
            [[thread.id]]
        );
        await new Promise((resolve) => {
            this.env.services.action.doAction(action, { onClose: resolve });
        });
        this.store.Thread.insert({
            model: this.props.threadModel,
            id: this.props.threadId,
        }).fetchNewMessages();
    },
});
