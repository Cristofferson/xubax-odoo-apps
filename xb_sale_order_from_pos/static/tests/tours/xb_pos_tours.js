// XUBAX - POS tour: create Quotation / Order / Layaway from the cart.
// Exercises the "Create Order" control button, the type choice, the delivery date
// asked for orders and layaways, and the ticket printed on creation.
// NOTE: uses demo data; it does NOT cover real fiscal positions or tax-included
// pricing (that parity is verified manually on a production copy).

import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as Notification from "@point_of_sale/../tests/generic_helpers/notification_util";
import { registry } from "@web/core/registry";

// The ticket printed on creation goes to the browser print: keep the print window away
// and check the ticket itself, which stays drawn in the receipt iframe.
function stubBrowserPrint() {
    return {
        content: "do not open the browser print window",
        trigger: ".pos",
        run: () => {
            posmodel.ticketPrinter._print = () => {};
        },
    };
}

function lastTicketHas(...texts) {
    return {
        content: `the printed ticket shows ${texts.join(", ")}`,
        trigger: "#receipt-iframe-container iframe",
        run: async () => {
            // The ticket is drawn while the register prints it: wait for it.
            let text = "";
            for (let attempt = 0; attempt < 50; attempt++) {
                const iframe = document.querySelector("#receipt-iframe-container iframe");
                text = iframe?.contentDocument?.body?.textContent || "";
                if (texts.every((wanted) => text.includes(wanted))) {
                    break;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
            }
            for (const wanted of texts) {
                if (!text.includes(wanted)) {
                    console.error(`[xb] ticket text: ${text}`);
                    throw new Error(`"${wanted}" is not on the printed ticket`);
                }
            }
            if (text.includes("Pro forma receipt")) {
                throw new Error("The ticket of a new order is not a pro forma receipt.");
            }
        },
    };
}

function selectOrderType(label) {
    return {
        content: `select order type '${label}'`,
        trigger: `.selection-item:contains("${label}")`,
        run: "click",
    };
}

function confirmDeliveryDate() {
    return {
        content: "keep the probable delivery date",
        trigger: ".modal .xb-delivery-date-confirm",
        run: "click",
    };
}

// One full cycle: add a product, set a customer, open the custom button and pick the
// given order type, then assert the success notification.
function createFromPos(product, partner, orderType, withDate) {
    return [
        ProductScreen.addOrderline(product, 1),
        ProductScreen.clickPartnerButton(),
        ProductScreen.clickCustomer(partner),
        ...ProductScreen.clickControlButton("Create Order"),
        selectOrderType(orderType),
        ...(withDate ? [confirmDeliveryDate()] : []),
        Notification.has("created from POS", "success"),
    ].flat();
}

registry.category("web_tour.tours").add("XbCreateOrderFlows", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),
            stubBrowserPrint(),

            // Flow 1: Quotation (no delivery date: it commits to nothing yet).
            createFromPos("Wall Shelf Unit", "Partner Test 1", "Quotation", false),
            lastTicketHas("QUOTATION", "Partner Test 1"),

            // Flow 2: Order (delivery date asked).
            createFromPos("Wall Shelf Unit", "Partner Test 1", "Order", true),
            lastTicketHas("ORDER", "Delivery date:"),

            // Flow 3: Layaway (delivery date asked, deadline on the ticket).
            createFromPos("Wall Shelf Unit", "Partner Test 1", "Layaway", true),
            lastTicketHas("LAYAWAY", "Pay the balance by:"),
        ].flat(),
});
