# POS Food Delivery: Uber Eats & DiDi Food (Mexico)

Direct integration between the Odoo 19 Restaurant Point of Sale and the two
main food delivery platforms in Mexico / LatAm — **no aggregator middleman,
no monthly per-order fees**.

## What it does

* **Menu sync**: publishes your POS catalog (categories, products, photos,
  attributes as modifier groups) to Uber Eats (Menu API v2) and DiDi Food
  (Open Platform v3), with an optional per-platform pricelist to compensate
  commissions. Prices are sent tax-included (IVA 16%).
* **Order intake**: platform webhooks create the order in the open POS
  session in real time. The POS rings (looping tone) and shows the order;
  the cashier accepts or rejects it (or use auto-accept). Orders flow to the
  kitchen like any other POS order.
* **Lifecycle**: accept → food ready → courier tracking (name/phone) →
  delivered, with cancellations handled both ways.
* **Payments**: each platform gets its own journal + POS payment method,
  registered automatically when the food is ready — sessions close clean.
  Cash orders (Mexico) are supported, including cash pickup collected at the
  store.
* **Sold-out control**: toggle a product per platform and it is 86'd on the
  platform in seconds.
* **Security**: per-account secret webhook URLs + platform signatures
  (Uber: HMAC-SHA256 `X-Uber-Signature`; DiDi: MD5 `didi-header-sign`),
  30-day request log.
* **Demo mode**: simulate a full delivery order without any credentials
  (Food Delivery ▸ Simulate Order).

## Requirements

* Odoo 19 (Community or Enterprise), `point_of_sale` + `pos_restaurant`.
* A server reachable over HTTPS (webhooks).
* Platform credentials:
  * **Uber Eats**: an approved app on developer.uber.com (Eats Marketplace
    API). Uber gates production access (NDA + certification).
  * **DiDi Food**: an app on developer.didi-food.com (app_id / app_secret),
    with the store bound to your app (self-service authorization page).

## Setup (short version)

1. Point of Sale ▸ Food Delivery ▸ Delivery Platforms ▸ create one account
   per platform per store; enter credentials + Store ID.
2. Register the account's webhook URL (Webhook tab) on the platform portal.
3. Test Connection ▸ Synchronize Menu ▸ Go Online.
4. Open your POS session and take orders.

## Support

cristofferson28@gmail.com — XUBAX / Cristofferson Reyes Rodriguez.
License: OPL-1.
