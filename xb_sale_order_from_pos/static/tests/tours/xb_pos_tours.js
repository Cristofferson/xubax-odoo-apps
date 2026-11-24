/** @odoo-module **/
// XUBAX - POS tour: create Quotation / Order / Layaway from the cart, then take the
// layaway's down payment from the list of orders and check the receipt.
// NOTE: uses test data; it does NOT cover real fiscal positions or tax-included
// pricing (that parity is verified manually on a production copy).

import * as ProductScreenPos from "@point_of_sale/../tests/tours/helpers/ProductScreenTourMethods";
import * as ProductScreenSale from "@pos_sale/../tests/helpers/ProductScreenTourMethods";
import * as PaymentScreen from "@point_of_sale/../tests/tours/helpers/PaymentScreenTourMethods";
import * as ReceiptScreen from "@point_of_sale/../tests/tours/helpers/ReceiptScreenTourMethods";
import * as NumberPopup from "@point_of_sale/../tests/tours/helpers/NumberPopupTourMethods";
import * as SelectionPopup from "@point_of_sale/../tests/tours/helpers/SelectionPopupTourMethods";
import { registry } from "@web/core/registry";

const ProductScreen = { ...ProductScreenPos, ...ProductScreenSale };

function clickCreateOrder() {
    return [
        {
            content: "click the 'Create Order' control button",
            trigger: ".control-button.o_xb_create_sale_order_button",
        },
    ];
}

function confirmDeliveryDate() {
    return [
        {
            content: "the delivery date is asked",
            trigger: ".modal-dialog .popup .modal-title:contains('Delivery date')",
            run: () => {},
        },
        {
            content: "confirm the proposed delivery date",
            trigger: ".modal-dialog .popup .button.confirm",
        },
    ];
}

function notificationHas(text) {
    return [
        {
            content: `notification '${text}'`,
            trigger: `.o_pos_notification_manager .o_notification:contains("${text}")`,
            run: () => {},
        },
    ];
}

// One full cycle: add a product, set a customer, open the custom button and
// pick the given order type, then assert the success notification and the fresh cart.
function createFromPos(product, partner, orderType, askDate) {
    return [
        ProductScreen.addOrderline(product, 1),
        ProductScreen.clickPartnerButton(),
        ProductScreen.clickCustomer(partner),
        clickCreateOrder(),
        SelectionPopup.clickItem(orderType),
        askDate ? confirmDeliveryDate() : [],
        notificationHas("created from POS"),
        ProductScreen.orderIsEmpty(),
    ].flat();
}

registry.category("web_tour.tours").add("XbCreateOrderFlows", {
    test: true,
    url: "/pos/ui",
    steps: () =>
        [
            ProductScreen.confirmOpeningPopup(),

            // Flow 1: Quotation.
            createFromPos("Wall Shelf Unit", "Partner Test 1", "Quotation", false),
            // Flow 2: Order (asks the delivery date).
            createFromPos("Wall Shelf Unit", "Partner Test 1", "Order", true),
            // Flow 3: Layaway (asks the delivery date).
            createFromPos("Wall Shelf Unit", "Partner Test 1", "Layaway", true),

            // Down payment on the layaway (the newest order, first in the list).
            {
                content: "the loader reads 'View Orders/Layaways'",
                trigger: ".control-button.o_sale_order_button:contains('View Orders/Layaways')",
            },
            {
                content: "select the layaway",
                trigger: ".order-row .col.name:first",
            },
            SelectionPopup.clickItem("Apply a down payment (fixed amount)"),
            NumberPopup.enterValue("1"),
            NumberPopup.clickConfirm(),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            {
                content: "the receipt is titled LAYAWAY",
                trigger: ".pos-receipt .xb-so-type:contains('LAYAWAY')",
                run: () => {},
            },
            {
                content: "the receipt shows the balance after the down payment",
                trigger: ".pos-receipt .xb-so-summary:contains('Balance due'):contains('0.98')",
                run: () => {},
            },
            ReceiptScreen.clickNextOrder(),
        ].flat(),
});
