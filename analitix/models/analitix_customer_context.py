# -*- coding: utf-8 -*-
"""What the shop knows about a customer, assembled at the door.

Scenario F of the brief: a recognised customer walks in and the screen greets
them by name with something relevant. Doing that well means pulling three
sources together, because any one of them alone produces a greeting that reads
like a mail merge:

* **CRM** — is there an open opportunity, and at what stage;
* **POS history** — what they have actually bought, which is what makes a
  suggestion land instead of guessing;
* **Special dates** — the ``xb.wish`` family already in production, so an
  anniversary or a birthday is a reason to say something rather than a field
  nobody reads.

The social privacy rule
-----------------------
A screen that says "Welcome back, Gustavo" while Gustavo is standing there with
somebody has just told that person something about him — that he shops here,
how often, possibly what he spends. Whether that matters is not ours to assume,
so the default is: **greet by name only when they arrived alone.** With company,
the screen stays neutral and the personal greeting goes to the salesperson,
who can use it face to face where it belongs.

The window for "arrived with someone" is per store, because a wide automatic
door and a narrow one produce different gaps.

Soft dependencies
-----------------
``xb.wish`` is XUBAX's own addon and is not declared a dependency: this app is
sold to stores that do not have it. It is detected at runtime and simply
contributes nothing when absent.
"""
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AnalitixCustomerContext(models.AbstractModel):
    """Service model: ``self.env['analitix.customer.context']``."""
    _name = "analitix.customer.context"
    _description = "Analitix — Customer Context"

    @api.model
    def build(self, store, partner, visitor=None):
        """Return everything worth saying to or about this customer.

        A dict rather than a record: nothing here is worth persisting, it is
        assembled fresh each time from sources that are already the truth.
        """
        if not partner:
            return {}
        context = {
            "partner": partner,
            "name": partner.name,
            "alone": self._is_alone(store, visitor),
            "crm": self._crm(partner),
            "purchases": self._purchases(store, partner),
            "occasion": self._occasion(partner),
        }
        context["screen_message"] = self._screen_message(store, context)
        context["staff_message"] = self._staff_message(context)
        return context

    # ------------------------------------------------------------------
    def _is_alone(self, store, visitor):
        """True when nobody arrived with them.

        Reads the purchase unit frozen at the door in phase 2 — the same
        decision, reused, rather than a second and possibly disagreeing answer
        to "were they together".
        """
        if not visitor:
            return True
        group = visitor.visit_group_id
        if group and group.size > 1:
            return False
        # Belt and braces for a store with grouping switched off: anyone else
        # who came through the same door within the window counts as company.
        if not group:
            from datetime import timedelta
            window = timedelta(seconds=store.welcome_group_seconds)
            others = self.env["analitix.visitor"].sudo().search_count([
                ("store_id", "=", store.id),
                ("door_id", "=", visitor.door_id.id),
                ("id", "!=", visitor.id),
                ("entered_at", ">=", visitor.entered_at - window),
                ("entered_at", "<=", visitor.entered_at + window),
            ])
            return not others
        return True

    def _crm(self, partner):
        """The open opportunity, if there is one."""
        lead = self.env["crm.lead"].sudo().search([
            ("partner_id", "=", partner.id),
            ("type", "=", "opportunity"),
            ("active", "=", True),
        ], order="priority desc, id desc", limit=1)
        if not lead:
            return {}
        return {
            "lead": lead,
            "name": lead.name,
            "stage": lead.stage_id.name,
            "expected": lead.expected_revenue,
        }

    def _purchases(self, store, partner, limit=3):
        """What they have actually bought here.

        Scoped to this store's own sales: on a shared instance, telling a
        salesperson what a customer bought at another company's shop would be
        exactly the leak the tenancy rules exist to prevent.
        """
        domain = [
            ("partner_id", "=", partner.id),
            ("state", "in", ("paid", "done", "invoiced")),
            ("company_id", "=", store.company_id.id),
        ]
        if store.match_mode == "registers" and store.register_ids:
            domain.append(("config_id", "in", store.register_ids.ids))
        orders = self.env["pos.order"].sudo().search(
            domain, order="date_order desc", limit=limit)
        if not orders:
            return {}
        last = orders[0]
        products = last.lines.mapped("product_id.name")[:2]
        return {
            "orders": orders,
            "count": len(orders),
            "last_date": last.date_order,
            "last_total": last.amount_total,
            "last_products": products,
        }

    def _occasion(self, partner):
        """A birthday or anniversary, from the special-dates addon if present.

        Detected at runtime rather than declared: Analitix is sold to stores
        that do not have that addon, and a hard dependency would make it
        uninstallable for them.
        """
        Reminder = self.env.get("xb.wish.reminders")
        if Reminder is None:
            return {}
        try:
            due = Reminder.sudo().search([
                ("partner_id", "=", partner.id),
                ("active", "=", True),
                ("is_due_today", "=", True),
            ], limit=1)
            if not due:
                return {}
            return {"kind": due.wish_type.name, "reminder": due}
        except Exception:  # noqa: BLE001
            # A different version of that addon, or a field that moved. Not
            # worth failing a greeting over.
            _logger.debug("Analitix: could not read special dates.", exc_info=True)
            return {}

    # ------------------------------------------------------------------
    def _screen_message(self, store, context):
        """What the screen may say — which is sometimes nothing personal."""
        if store.welcome_alone_only and not context["alone"]:
            return ""
        name = context["name"]
        occasion = context.get("occasion") or {}
        if occasion.get("kind"):
            return _("Welcome back, %(name)s — happy %(occasion)s!",
                     name=name, occasion=occasion["kind"])
        purchases = context.get("purchases") or {}
        if purchases.get("last_products"):
            return _("Welcome back, %(name)s", name=name)
        return _("Welcome back, %(name)s", name=name)

    def _staff_message(self, context):
        """The line the salesperson reads on their phone.

        Denser than the screen's, because it is for someone who is about to
        walk over and talk to this person.
        """
        parts = [_("%s is a returning customer.", context["name"])]
        occasion = context.get("occasion") or {}
        if occasion.get("kind"):
            parts.append(_("Today is their %s.", occasion["kind"]))
        purchases = context.get("purchases") or {}
        if purchases.get("last_date"):
            products = ", ".join(purchases.get("last_products") or [])
            parts.append(_(
                "Last bought %(products)s on %(date)s (%(total).2f).",
                products=products or _("something"),
                date=fields.Date.to_string(purchases["last_date"].date()),
                total=purchases["last_total"]))
        crm = context.get("crm") or {}
        if crm.get("name"):
            parts.append(_("Open opportunity: %(name)s (%(stage)s).",
                           name=crm["name"], stage=crm.get("stage") or ""))
        if not context["alone"]:
            parts.append(_("They are not alone — greet them in person rather "
                           "than letting the screen name them."))
        return " ".join(parts)
