# XUBAX — Sales, Quotations & Layaway from POS · Loyalty

**Author:** XUBAX · soporte@xubax.com · https://www.xubax.com
**License:** OPL-1 · **Odoo:** 19.0 · **Technical name:** `xb_sale_order_from_pos_loyalty`

When a quotation, order or layaway is created at the Point of Sale nothing is paid yet,
so no loyalty points are earned — but Odoo's ticket prints them as already **Won**. With
this add-on the ticket printed on **creation** says instead:

| Document | Ticket line |
|---|---|
| Quotation | You could earn **948.28** loyalty points if you confirm this quotation |
| Order | You will earn **948.28** loyalty points when this order is paid in full |
| Layaway | You will earn **948.28** loyalty points when this layaway is paid in full |

Advance and settlement tickets are real payments and keep Odoo's own line, as does every
regular sale. The same wording reaches the customer when a quotation ticket is sent by
WhatsApp or email, because what is sent is the printed ticket.

Installs by itself when both **Sales, Quotations & Layaway from POS**
(`xb_sale_order_from_pos`) and **Point of Sale Loyalty** (`pos_loyalty`) are installed.
Nothing to configure. The sentences are translated in `xb_sale_order_from_pos`
(Spanish: *Podrías ganar 948.28 puntos de lealtad si confirmas esta cotización* /
*Ganarás 948.28 puntos de lealtad al liquidar este pedido*).
