# XUBAX — Sales, Quotations & Layaway from POS · Loyalty

**Author:** XUBAX · soporte@xubax.com · https://www.xubax.com
**License:** OPL-1 · **Odoo:** 19.0 · **Technical name:** `xb_sale_order_from_pos_loyalty`

A quotation created at the Point of Sale earns no loyalty points yet, but Odoo's ticket
prints them as already **Won**. With this add-on, a **quotation** ticket reads:

> You could earn **948.28** loyalty points if you confirm this quotation

Every other ticket (sales, orders, layaways, settlements) keeps Odoo's own line untouched.
The same wording reaches the customer when the quotation ticket is sent by WhatsApp or
email, because what is sent is the printed ticket.

Installs by itself when both **Sales, Quotations & Layaway from POS**
(`xb_sale_order_from_pos`) and **Point of Sale Loyalty** (`pos_loyalty`) are installed.
Nothing to configure. The sentence is translated in `xb_sale_order_from_pos`
(Spanish: *Podrías ganar 948.28 puntos de lealtad si confirmas esta cotización*).
