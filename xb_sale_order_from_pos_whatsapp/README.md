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
