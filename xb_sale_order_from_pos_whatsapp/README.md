# XUBAX — Sales, Quotations & Layaway from POS · WhatsApp

**Author:** XUBAX · soporte@xubax.com · https://www.xubax.com
**License:** OPL-1 · **Odoo:** 19.0 Enterprise · **Technical name:** `xb_sale_order_from_pos_whatsapp`

Adds **WhatsApp** to the *How does the customer want the quotation?* question of
**Sales, Quotations & Layaway from POS** (`xb_sale_order_from_pos`). The customer receives
**the very ticket the POS prints**, as the image header of an approved WhatsApp template,
and the message stays in the quotation's chatter.

Installs by itself when both `xb_sale_order_from_pos` and Odoo Enterprise **WhatsApp**
(`whatsapp_sale`) are installed.

## Setup

1. Create a WhatsApp template in *WhatsApp ▸ Templates*:
   - **Applies to:** Sales Order · **Header type:** Image (upload a sample ticket: Meta
     asks for one to approve it; at send time the real ticket replaces it).
   - Body variables can use, besides the usual fields, two ready-to-read ones this add-on
     provides: **`xb_wa_amount_total`** (total with currency, e.g. `$ 12,500.00`) and
     **`xb_wa_validity_date`** (expiration date in the customer's language). A plain field
     would print `12500.0` and `2026-10-12`.
   - Submit it to Meta and wait until it is **Approved**.
2. *Settings ▸ Point of Sale ▸ this POS*: turn on **Ask how to deliver each quotation** and
   pick the template in **Quotation WhatsApp template** (only approved Sales Order
   templates with an Image header are listed).
3. Close and reopen the POS session: the POS reads its configuration when the session opens.

## Behaviour

- The WhatsApp option appears only at POS that have the template set.
- The number shown is the customer's; the cashier can change it. A number typed for a
  customer who had none is saved on the contact; an existing one is never overwritten.
- If WhatsApp rejects the message (invalid number, template not approved, account issue)
  the cashier sees why, and the other channels and the quotation are not affected.
- Sending runs as the cashier: to render the ticket message she needs read access to Sales
  Orders (e.g. *Sales / User: Own Documents Only*).

## WhatsApp notices about an order ("ready", "late"...)

**One button**, *Notify*, on each order / layaway: in the orders list (Sales, and the
list the POS opens to recover an order) and on the order form. Never on a plain
quotation. It opens a window where the seller picks what to tell the customer, reads the
exact message that will be sent and sends it:

- **The order is ready** — sends the company's *order ready* template (with the balance
  still due) and remembers when the customer was told. In the list the button then shows
  as *Notified*, and still opens the same window.
- **Reminder: it is waiting to be picked up** — once the customer was told it is ready
  (the window picks it by default then), with the company's *pick-up reminder* template.
- **Reminder: balance due** — orders and layaways with a balance still due, with the
  company's *balance due reminder* template.
- **We need to confirm a detail** — size, engraving, stone... The company's *confirm a
  detail* template asks the customer to reply: that opens the WhatsApp conversation, and
  from then on the seller can write freely for 24 hours.
- **There is a delay: new delivery date** — the seller picks the **new delivery date**
  and apologises with the company's *order late* template. The date is saved as the
  order's **Delivery Date** (`commitment_date`), so the promise is on the order for
  everyone, and the "ready" mark is cleared so *the order is ready* can be sent again
  when it really is.

Only the notices whose template the company has, and that make sense for the order, are
offered (no balance reminder on a paid order, no pick-up reminder before the "ready"
notice); with none, the button does not show at all.

Setup: create each template on **Sales Order** and have Meta approve it, then pick them
in *Settings ▸ Point of Sale* (**Order ready**, **Pick-up reminder**, **Balance due
reminder**, **Confirm a detail** and **Order late WhatsApp template**, per company). Besides the usual fields, template variables can use **`xb_wa_kind_label`**
("order" / "layaway"), **`xb_wa_amount_unpaid`** (balance due with currency) and
**`xb_wa_delivery_date`** (delivery date as the customer reads it: "sábado 26 de
septiembre" in Spanish, the year only when it is not this year).
