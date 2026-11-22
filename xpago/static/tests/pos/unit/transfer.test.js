import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-dom";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv, getFilledOrder } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import {
    formatClabe,
    minutesLeft,
    missingCustomerData,
    transferDelay,
    whatsappPhone,
    whatsappText,
    whatsappUrl,
} from "@xpago/pos/app/transfer/transfer_utils";

definePosModels();

describe("XPago transfer: helpers", () => {
    test("a CLABE reads in its four parts", () => {
        expect(formatClabe("738180000000012345")).toBe("738 180 00000001234 5");
        expect(formatClabe("12345")).toBe("12345");
        expect(formatClabe(null)).toBe("");
    });

    test("asks often at first, then less", () => {
        expect(transferDelay(0)).toBe(3000);
        expect(transferDelay(120000)).toBe(5000);
        expect(transferDelay(15 * 60000)).toBe(10000);
    });

    test("WhatsApp: phone with the country code, and the details in the message", () => {
        expect(whatsappPhone("443 123 4567")).toBe("524431234567");
        expect(whatsappPhone("+52 1 443 123 4567")).toBe("5214431234567");
        expect(whatsappPhone("12345")).toBe("");
        const view = {
            business: "Anello", clabe: "738180000000012345", bank: "STP", beneficiary: "XPago",
            concept: "", checkout_url: "https://pay.example/x",
        };
        const text = whatsappText(view, { amountText: "$ 10.00", clabeText: "738 180 00000001234 5", minutes: 30 });
        expect(text).toInclude("738180000000012345");
        expect(text).toInclude("$ 10.00");
        expect(text).toInclude("30 min");
        expect(text).not.toInclude("https://pay.example/x");
        expect(text).not.toInclude("Concept");
        expect(whatsappUrl("4431234567", "a b")).toBe("https://wa.me/524431234567?text=a%20b");
        expect(whatsappUrl("", "a")).toBe("https://wa.me/?text=a");
    });

    test("minutes left of the CLABE", () => {
        const now = Date.parse("2026-11-15T20:00:00Z");
        expect(minutesLeft("2026-11-15 20:59:30", now)).toBe(60);
        expect(minutesLeft("2026-11-15 19:00:00", now)).toBe(0);
        expect(minutesLeft(false, now)).toBe(null);
    });

    test("what the customer lacks for the CLABE", () => {
        expect(missingCustomerData({ name: "Ana Ruiz", email: "ana@x.mx", phone: "443 123 4567" })).toEqual([]);
        expect(missingCustomerData({ name: "Ana", email: "", phone: "123" }).length).toBe(2);
        expect(missingCustomerData(null).length).toBe(3);
    });
});

test("XPago transfer in the receipt", async () => {
    const store = await setupPosEnv();
    const order = await getFilledOrder(store);
    const method = store.models["pos.payment.method"].find((m) => m.name === "Card");
    const line = order.addPaymentline(method).data;
    method.use_payment_terminal = "xpago_spei";
    Object.assign(line, {
        card_no: "2345",
        card_type: "SPEI",
        payment_method_payment_mode: "SPEI",
        transaction_id: "pay-9",
        payment_ref_no: "777001",
        cardholder_name: "Ana Ruiz",
    });
    const receipt = await mountWithCleanup(OrderReceipt, { props: { order } });
    await animationFrame();
    expect(".xpago-transfer-receipt").toHaveCount(1);
    expect(".xpago-transfer-receipt").toHaveText(/PAID BY TRANSFER/);
    expect(".xpago-transfer-receipt").toHaveText(/CLABE: \*\*\*\* 2345/);
    expect(".xpago-transfer-receipt").toHaveText(/Operation: 777001/);
    expect(".xpago-transfer-receipt").not.toHaveText(/pay-9/);
    // No card voucher for a transfer.
    expect(".xpago-voucher").toHaveCount(0);
    method.use_payment_terminal = "xpago";
    expect(receipt.xpagoTransferLines).toHaveLength(0);
});
