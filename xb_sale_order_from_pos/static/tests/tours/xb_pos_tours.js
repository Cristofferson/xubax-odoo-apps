/** @odoo-module **/
// XUBAX - POS tour: create Quotation / Order / Layaway from the cart (Odoo 18).
// Exercises the custom "Create Order" control button, the three options of the
// SelectionPopup and the delivery-date question asked for orders and layaways,
// asserting the success notification and the emptied cart for each flow.
// NOTE: uses demo data; it does NOT cover real fiscal positions or tax-included
// pricing (that parity is verified manually on a production copy).

import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as Notification from "@point_of_sale/../tests/tours/utils/generic_components/notification_util";
import { registry } from "@web/core/registry";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

// Pick an order type from the custom SelectionPopup ("Create from POS").
function selectOrderType(label) {
    return {
        content: `select order type '${label}'`,
        trigger: `.modal .selection-item:contains("${label}")`,
        run: "click",
    };
}

// The delivery date asked for orders and layaways: leave it empty.
function noDeliveryDate() {
    return {
        content: "no delivery date",
        trigger: `.modal .modal-footer button:contains("No date")`,
        run: "click",
    };
}

// One full cycle: add a product, set a customer, open the custom button and
// pick the given order type, then assert the success notification and that the
// consumed cart was replaced by an empty one.
function createFromPos(product, partner, orderType, askDate) {
    return [
        ProductScreen.addOrderline(product, 1),
        ProductScreen.clickPartnerButton(),
        ProductScreen.clickCustomer(partner),
        ...ProductScreen.clickControlButton("Create Order"),
        selectOrderType(orderType),
        ...(askDate ? [noDeliveryDate()] : []),
        Notification.has("created from POS", "success"),
        ProductScreen.orderIsEmpty(),
    ].flat();
}

// Render the receipt of the current cart as if it were a layaway with a balance:
// type header, customer, summary, balance and payment QR must all be there.
function checkLayawayReceipt() {
    return {
        content: "render a layaway receipt",
        trigger: ".product-screen",
        run: async () => {
            const pos = window.posmodel;
            const order = pos.get_order();
            pos.config.xb_enrich_receipt = true;
            pos.config.xb_show_portal_link = true;
            order.uiState.xbSaleOrder = {
                sale_order_id: 1,
                name: "S99999",
                amount_total: 1000,
                amount_unpaid: 900,
                portal_url: "https://example.com/my/orders/1?access_token=x",
                partner_ref: "REF1",
                commitment_date: false,
                layaway_deadline: "2030-01-31",
                type: "layaway",
            };
            try {
                const html = await pos.env.services.renderer.toHtml(OrderReceipt, {
                    data: pos.orderExportForPrinting(order),
                    formatCurrency: pos.env.utils.formatCurrency,
                });
                const text = html.outerHTML;
                for (const needle of ["LAYAWAY", "S99999", "REF1", "Balance due", "xb-so-portal-qr", "Pay the balance by"]) {
                    if (!text.includes(needle)) {
                        throw new Error(`receipt misses ${needle}`);
                    }
                }
            } finally {
                delete order.uiState.xbSaleOrder;
                pos.config.xb_enrich_receipt = false;
                pos.config.xb_show_portal_link = false;
            }
        },
    };
}

registry.category("web_tour.tours").add("XbCreateOrderFlows", {
    steps: () =>
        [
            Chrome.startPoS(),
            Dialog.confirm("Open Register"),

            // The receipt of a layaway with a balance.
            ProductScreen.addOrderline("Wall Shelf Unit", 1),
            ProductScreen.clickPartnerButton(),
            ProductScreen.clickCustomer("Partner Test 1"),
            checkLayawayReceipt(),
            ProductScreen.clickNumpad("⌫"),
            ProductScreen.clickNumpad("⌫"),
            ProductScreen.orderIsEmpty(),

            // Flow 1: Quotation.
            createFromPos("Wall Shelf Unit", "Partner Test 1", "Quotation", false),

            // Flow 2: Order (no advance).
            createFromPos("Wall Shelf Unit", "Partner Test 1", "Order", true),

            // Flow 3: Layaway (with advance — needs the down-payment product).
            createFromPos("Wall Shelf Unit", "Partner Test 1", "Layaway", true),
        ].flat(),
});
