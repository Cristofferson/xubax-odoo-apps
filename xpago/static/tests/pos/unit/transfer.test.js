import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-dom";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { setupPosEnv, getFilledOrder } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import {
    customerDefaults,
    formatClabe,
    minutesLeft,
    transferDelay,
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

    test("minutes left of the CLABE", () => {
        const now = Date.parse("2026-11-15T20:00:00Z");
        expect(minutesLeft("2026-11-15 20:59:30", now)).toBe(60);
        expect(minutesLeft("2026-11-15 19:00:00", now)).toBe(0);
        expect(minutesLeft(false, now)).toBe(null);
    });

    test("who pays: the customer, else the business", () => {
        const company = { email: "tienda@anello.mx", phone: "4431234567" };
        expect(customerDefaults({ name: "Ana Ruiz", email: "ana@x.mx", phone: "5512345678" }, company)).toEqual({
            name: "Ana Ruiz", email: "ana@x.mx", phone: "5512345678", isBusiness: false,
        });
        expect(customerDefaults(null, company)).toEqual({
            name: "", email: "tienda@anello.mx", phone: "4431234567", isBusiness: true,
        });
        // A customer without email nor phone keeps the name; the business's contact fills the rest.
        expect(customerDefaults({ name: "Ana" }, company).name).toBe("Ana");
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
