import { test, expect } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-dom";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv, getFilledOrder } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";

definePosModels();

async function paidWithXpago(cardType) {
    const store = await setupPosEnv();
    const order = await getFilledOrder(store);
    Object.assign(order.config, {
        xpago_voucher_on_receipt: true,
        xpago_voucher_merchant: "1234567",
        xpago_voucher_credit_text: "Por este pagaré me obligo",
        xpago_voucher_debit_text: "Autorizo que se cargue a mi cuenta",
        xpago_voucher_signature: true,
    });
    const method = store.models["pos.payment.method"].find((m) => m.name === "Card");
    const line = order.addPaymentline(method).data;
    method.use_payment_terminal = "xpago";
    Object.assign(line, {
        card_brand: "VISA",
        card_no: "4242",
        card_type: cardType,
        payment_method_authcode: "A1B2C3",
        payment_method_issuer_bank: "BBVA",
        transaction_id: "pay-1",
        payment_ref_no: "888002",
    });
    return order;
}

test("XPago card voucher in the receipt", async () => {
    const order = await paidWithXpago("CREDIT");
    const receipt = await mountWithCleanup(OrderReceipt, { props: { order } });
    await animationFrame();
    expect(".xpago-voucher").toHaveCount(1);
    expect(".xpago-voucher").toHaveText(/CARD SALE/);
    expect(".xpago-voucher").toHaveText(/VISA \*\*\*\* 4242/);
    expect(".xpago-voucher").toHaveText(/Credit/);
    expect(".xpago-voucher").toHaveText(/Authorization: A1B2C3/);
    // The operation the processor gave; its internal id stays out of the customer's ticket.
    expect(".xpago-voucher").toHaveText(/Operation: 888002/);
    expect(".xpago-voucher").not.toHaveText(/pay-1/);
    expect(".xpago-voucher").not.toHaveText(/Reference/);
    expect(".xpago-voucher").toHaveText(/Merchant number: 1234567/);
    expect(".xpago-voucher").toHaveText(/Por este pagaré me obligo/);
    expect(".xpago-voucher").toHaveText(/Customer's signature/);

    // A debit card carries the debit legend.
    const line = order.payment_ids[0];
    line.card_type = "DEBIT";
    expect(receipt.xpagoFunding(line)).toBe("Debit");
    expect(receipt.xpagoLegend(line)).toBe("Autorizo que se cargue a mi cuenta");

    // Chip and contactless are never signed; a swiped card is, while the option is on.
    expect(receipt.xpagoNeedsSignature(line)).toBe(true);
    line.payment_method_payment_mode = "CHIP";
    expect(receipt.xpagoNeedsSignature(line)).toBe(false);
    line.payment_method_payment_mode = "CONTACTLESS";
    expect(receipt.xpagoNeedsSignature(line)).toBe(false);
    line.payment_method_payment_mode = "SWIPE";
    expect(receipt.xpagoNeedsSignature(line)).toBe(true);
    order.config.xpago_voucher_signature = false;
    expect(receipt.xpagoNeedsSignature(line)).toBe(false);
    order.config.xpago_voucher_signature = true;

    // No voucher when it is turned off, nor for a card that is not XPago's.
    expect(receipt.xpagoVoucherLines).toHaveLength(1);
    order.config.xpago_voucher_on_receipt = false;
    expect(receipt.xpagoVoucherLines).toHaveLength(0);
    order.config.xpago_voucher_on_receipt = true;
    line.payment_method_id.use_payment_terminal = false;
    expect(receipt.xpagoVoucherLines).toHaveLength(0);
});
