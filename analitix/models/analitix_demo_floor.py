# -*- coding: utf-8 -*-
"""Demo content for the parts of the product that need a shop to exist.

Phase 6 asks for demo data complete enough to reproduce every screenshot and
every screencast **without hardware**, and that is a higher bar than "the module
installs". A conversion dashboard with traffic and no tickets is a flat line at
zero; a lost-sale screen with no lost sales teaches a prospective buyer nothing
except that the feature might not work.

So this builds the rest of a plausible fortnight: POS orders that follow the
same day curve as the traffic, a floor divided into zones with displays on it, a
salesperson on a rota, walk-outs — some rescued, some not — and one closed
monthly report.

Two rules hold throughout, and they are what make the screenshots reproducible:

* **Nothing is random.** Every figure is derived arithmetically from the hour
  and the weekday, so the same database regenerated next month produces the same
  curve and the same numbers.
* **Nothing is flattering.** The demo conversion rate sits in the low twenties,
  which is what a real jewellery boutique looks like, and roughly a third of the
  walk-outs are never rescued. A demo where the team catches everything would be
  a sales lie that the first week of real data exposes.
"""
import logging
from datetime import timedelta

import pytz

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AnalitixStore(models.Model):
    _inherit = "analitix.store"

    # ------------------------------------------------------------------
    @api.model
    def _generate_demo_floor(self, store_ids):
        """Zones, displays, a rota, sales, walk-outs and one report."""
        stores = self.browse(store_ids).exists()
        if not stores:
            return True
        for store in stores:
            store._demo_zones()
        self.env.flush_all()
        for store in stores:
            store._demo_sales()
        self.env.flush_all()
        for store in stores:
            store._demo_walkouts()
        self.env.flush_all()
        for store in stores:
            store._demo_report()
        stores._demo_heartbeats()
        return True

    def _demo_heartbeats(self):
        """Make the demo fleet look alive.

        Without this every demo store opens showing "Down" on every device,
        which is indistinguishable from a broken installation — and it is the
        first screen anybody sees.
        """
        now = fields.Datetime.now()
        for store in self:
            for index, device in enumerate(store.device_ids):
                device.sudo().write({
                    # Staggered by a few seconds, because a fleet whose
                    # heartbeats all land on the same instant is the one thing
                    # a real fleet never does.
                    "last_heartbeat": now - timedelta(seconds=5 + index * 7),
                })

    def _demo_clock(self):
        """The store's own local clock, plus a converter back to UTC.

        A shop trades 10:00–20:00 in ITS timezone. Writing those hours as UTC
        puts a Mexican boutique's evening peak at four in the morning, and when
        the server is past midnight UTC while the shop is still open it makes
        "today" empty — which is what a broken installation looks like.
        """
        self.ensure_one()
        tz = pytz.timezone(self.tz or "UTC")
        local_now = pytz.utc.localize(fields.Datetime.now()).astimezone(
            tz).replace(minute=0, second=0, microsecond=0, tzinfo=None)

        def to_utc(stamp):
            return tz.localize(stamp).astimezone(pytz.utc).replace(tzinfo=None)

        return local_now, to_utc

    # ------------------------------------------------------------------
    def _demo_zones(self):
        """A floor plan, plus who covers the counter."""
        self.ensure_one()
        Zone = self.env["analitix.zone"].sudo()
        if Zone.search_count([("store_id", "=", self.id)]):
            return

        plan = [
            # (code, name, kind, engaged, lost-sale, alert)
            ("R", "Engagement Rings", "display", 25, 180, True),
            ("W", "Watches", "display", 20, 200, True),
            ("F", "Fitting / Try-on", "fitting", 40, 600, False),
            ("C", "Checkout", "checkout", 15, 240, True),
        ]
        zones = Zone.create([{
            "store_id": self.id, "code": code, "name": name, "kind": kind,
            "engaged_seconds": engaged, "lost_sale_seconds": lost,
            "alert_on_dwell": alert,
        } for code, name, kind, engaged, lost, alert in plan])

        # Displays, with real products on them where the demo database has any.
        # Without the products the attention figures cannot be crossed against
        # sales, which is the whole point of the feature.
        products = self.env["product.product"].sudo().search(
            [("available_in_pos", "=", True)], limit=6)
        showcases = [
            ("Window Showcase", zones[0], 8),
            ("Solitaire Case", zones[0], 10),
            ("New Arrivals Table", zones[1], 8),
        ]
        Poi = self.env["analitix.poi"].sudo()
        for index, (name, zone, stop) in enumerate(showcases):
            Poi.create({
                "store_id": self.id, "zone_id": zone.id, "name": name,
                "stop_seconds": stop,
                "product_ids": [(6, 0, products[index:index + 2].ids)],
            })

        # Somebody has to be on the floor, or every alert in the demo escalates
        # to the fallback and the routing looks broken rather than unstaffed.
        seller = self._demo_seller()
        if seller:
            self.env["analitix.zone.vendor"].sudo().create([{
                "zone_id": zone.id, "user_id": seller.id,
                "weekday": "all", "hour_from": 9.0, "hour_to": 21.0,
            } for zone in zones if zone.alert_on_dwell])
            if not self.alert_fallback_user_id:
                self.alert_fallback_user_id = seller.id

    def _demo_seller(self):
        """A demo salesperson, created once and shared by both demo stores."""
        Users = self.env["res.users"].sudo()
        login = "analitix.demo.seller"
        seller = Users.with_context(active_test=False).search(
            [("login", "=", login)], limit=1)
        if seller:
            return seller
        try:
            return Users.with_context(no_reset_password=True).create({
                "name": "Rosa Márquez (demo)",
                "login": login,
                "group_ids": [
                    (4, self.env.ref("base.group_user").id),
                    (4, self.env.ref("analitix.group_user").id),
                ],
            })
        except Exception:  # noqa: BLE001
            _logger.info("Analitix demo: could not create the demo salesperson.")
            return Users.browse()

    # ------------------------------------------------------------------
    def _demo_sales(self, days=14):
        """POS orders shaped like the traffic, so conversion is believable.

        Attribution is by register rather than by company: the demo database
        ships with Odoo's own POS demo orders, and in company mode those would
        be swept into this store's conversion rate and make the number
        meaningless.
        """
        self.ensure_one()
        Order = self.env["pos.order"].sudo()
        config = self._demo_register()
        if not config:
            return
        session = self.env["pos.session"].sudo().search(
            [("config_id", "=", config.id)], order="id desc", limit=1)
        if not session or Order.search_count([("session_id", "=", session.id)]):
            return

        product = self.env["product.product"].sudo().search(
            [("available_in_pos", "=", True)], limit=1)
        if not product:
            return
        pricelist = self.env["product.pricelist"].sudo().search(
            [("currency_id", "=", self.company_id.currency_id.id)], limit=1)

        local_now, to_utc = self._demo_clock()
        # The traffic generator scales a store's visitors by its floor area, so
        # the ticket count has to scale by the same factor or the bigger store
        # reads at half the conversion of the smaller one for no reason a
        # prospective buyer could work out. The small per-store offset keeps the
        # two demo stores from landing on identical figures, which looks
        # fabricated the moment somebody puts the two reports side by side.
        size = 1 + self.area_sqm / 200.0
        offset = 0.9 + (self.id % 5) * 0.05
        vals_list = []
        for day_offset in range(days, -1, -1):
            day = local_now - timedelta(days=day_offset)
            busy = 1.5 if day.weekday() >= 5 else 1.0
            last_hour = local_now.hour if day_offset == 0 else 20
            for hour in range(10, min(last_hour, 20) + 1):
                shape = max(1.0 + 0.6 * (1 - abs(hour - 13) / 4.0)
                            + 0.9 * (1 - abs(hour - 19) / 4.0), 0.3)
                # Roughly a quarter of the hour's visitors buy — the figure a
                # real speciality retailer sees, not a flattering one.
                tickets = int(1.45 * shape * busy * size * offset)
                for n in range(tickets):
                    # A spread of basket sizes that is not random: bigger tickets
                    # in the evening, when the demo curve peaks.
                    total = 1200.0 + 340.0 * ((hour + n) % 5) + (600.0 if hour >= 18 else 0.0)
                    units = 1 + ((hour + n) % 3)
                    vals_list.append({
                        "session_id": session.id,
                        "company_id": self.company_id.id,
                        "pricelist_id": pricelist.id if pricelist else False,
                        "date_order": to_utc(
                            day.replace(hour=hour, minute=(n * 13) % 60)),
                        "amount_tax": 0.0,
                        "amount_total": total,
                        "amount_paid": total,
                        "amount_return": 0.0,
                        "state": "paid",
                        "lines": [(0, 0, {
                            "product_id": product.id,
                            "qty": units,
                            "price_unit": total / units,
                            "price_subtotal": total,
                            "price_subtotal_incl": total,
                        })],
                    })
        if vals_list:
            Order.create(vals_list)

    def _demo_register(self):
        """A register of this store's own, opened once."""
        self.ensure_one()
        if self.register_ids:
            config = self.register_ids[:1]
        else:
            config = self.env["pos.config"].sudo().create({
                "name": "%s — Register" % self.name,
                "company_id": self.company_id.id,
            })
            self.write({"match_mode": "registers",
                        "register_ids": [(4, config.id)]})
        if not config.current_session_id:
            try:
                config.with_user(self.env.ref("base.user_admin")).open_ui()
            except Exception:  # noqa: BLE001
                _logger.info(
                    "Analitix demo: could not open a POS session for %s.",
                    self.display_name)
                return self.env["pos.config"].browse()
        return config

    # ------------------------------------------------------------------
    def _demo_walkouts(self, days=14):
        """Walk-outs with their alerts, some rescued and some not.

        The ratio is deliberate. A demo where the team catches every walk-out
        would make the monthly report look magnificent and would be a lie the
        customer's first real week exposes.
        """
        self.ensure_one()
        Lost = self.env["analitix.lost.sale"].sudo()
        if Lost.search_count([("store_id", "=", self.id)]):
            return
        zones = self.env["analitix.zone"].sudo().search(
            [("store_id", "=", self.id), ("alert_on_dwell", "=", True)])
        if not zones:
            return
        seller = self._demo_seller()
        Alert = self.env["analitix.alert"].sudo()
        average = self._average_ticket(days=30) or 1800.0

        local_now, to_utc = self._demo_clock()
        # Offset the pattern per store. Without it both demo stores report the
        # same walk-out count and the same recovered amount to the cent, which
        # is the first thing anybody notices when they open the two monthly
        # reports side by side — and it reads as invented, because it is.
        seed = self.id % 3
        for day_offset in range(days, 0, -1):
            day = local_now - timedelta(days=day_offset)
            # Two or three a day, at the hours a shop is actually busy.
            for index, hour in enumerate((12, 17, 19)):
                if (day_offset + index + seed) % 4 == 0:
                    continue
                zone = zones[(day_offset + index) % len(zones)]
                when = to_utc(day.replace(hour=hour, minute=(index * 17) % 60))
                # Two in three are reached in time. The rest are the number the
                # product exists to show the owner.
                rescued = (day_offset + index + seed) % 3 != 0
                alert = Alert.create({
                    "store_id": self.id,
                    "zone_id": zone.id,
                    "kind": "lost_sale",
                    "summary": "Somebody has been at %s for %d minutes and "
                               "nobody has been over." % (zone.name, 4 + index),
                    "user_id": seller.id if seller else False,
                    "sent_at": when,
                    "sent_app": True,
                    "acknowledged": rescued,
                    "acknowledged_at": when + timedelta(seconds=45 + index * 30)
                                       if rescued else False,
                    "outcome": "sold" if rescued else "missed",
                })
                Lost.create({
                    "store_id": self.id,
                    "zone_id": zone.id,
                    "detected_at": when,
                    "dwell_seconds": zone.lost_sale_seconds + 40 + index * 25,
                    "was_served": False,
                    "state": "rescued" if rescued else "lost",
                    "alert_id": alert.id,
                    "estimated_value": average,
                })

    # ------------------------------------------------------------------
    def _demo_report(self):
        """One closed monthly report, so the ROI screen is not empty."""
        self.ensure_one()
        if not self.value_report_enabled:
            return
        Report = self.env["analitix.value.report"].sudo()
        if Report.search_count([("store_id", "=", self.id)]):
            return
        today = fields.Date.context_today(self)
        first_this = today.replace(day=1)
        end = first_this - timedelta(days=1)
        start = end.replace(day=1)
        try:
            Report.build(self, start, end)
        except Exception:  # noqa: BLE001
            _logger.info("Analitix demo: could not build the value report for %s.",
                         self.display_name)
