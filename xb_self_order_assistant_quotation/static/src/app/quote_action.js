/**
 * XUBAX - Virtual seller + kiosk quotation: the seller opens the kiosk's own quotation window
 * (printed at the kiosk or sent to WhatsApp) for what the customer has in the cart.
 */
import { xbVaActions } from "@xb_self_order_assistant/app/assistant";
import { XbQuoteDialog } from "@xb_self_order_quotation/app/quotation";

xbVaActions.kiosk_quote = (seller, action) => {
    if (!seller.selfOrder.currentOrder.lines.length) {
        return;
    }
    seller.dock();
    seller.dialog.add(XbQuoteDialog, { modo: action.mode === "whatsapp" ? "whatsapp" : "print" });
};
