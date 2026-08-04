# -*- coding: utf-8 -*-
"""Every screen, opened by every role, with nothing but that role's rights.

This file exists because 263 tests missed a bug that made the product's main
configuration screen unusable for the role it was built for. An Analitix
Manager who was not also a Point of Sale user got an *Access Error* opening
their own store: the form shows ``register_ids``, and reading ``pos.config``
needs the POS group.

The reason the suite could not see it is worth stating plainly, because it
applies to any Odoo addon: tests run with an environment whose user is far more
privileged than a customer's. Asserting business logic through ``sudo`` or
through the test user proves the logic and says nothing about whether a real
salesperson can open the page.

So this does the one thing the rest of the suite does not: it resolves every
action the addon ships, reads its views as each role, and touches the comodel
behind every relational field on them. A field pointing at a model the role
cannot read is exactly what produced the original failure, and it is now a test
failure instead of a customer's first afternoon.
"""
from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

#: Actions every listed role must be able to open. Menu visibility is not the
#: same question — a role may legitimately not see a menu — so this asserts on
#: what the role IS given, per the menus in views/analitix_menus.xml.
SCREENS = {
    "analitix.group_user": [
        "analitix.action_hourly",
        "analitix.action_door_hourly",
        "analitix.action_visitor",
        "analitix.action_demographic",
        "analitix.action_visit_group",
        "analitix.action_lost_sale",
        "analitix.action_zone_dwell",
        "analitix.action_poi_performance",
        "analitix.action_value_report",
        "analitix.action_coaching",
        "analitix.action_recurrence",
        "analitix.action_store",
        "analitix.action_alert_mine",
    ],
    "analitix.group_technician": [
        "analitix.action_device_health",
        "analitix.action_event",
        "analitix.action_job",
        "analitix.action_audit_log",
        "analitix.action_anomaly",
    ],
    "analitix.group_manager": [
        "analitix.action_store",
        "analitix.action_door",
        "analitix.action_device",
        "analitix.action_zone",
        "analitix.action_poi",
        "analitix.action_signage_rule",
        "analitix.action_staff_signature",
        "analitix.action_sale_match",
        "analitix.action_signage_event",
        "analitix.action_face_signature",
        "analitix.action_store_daily",
    ],
    "analitix.group_regional": [
        "analitix.action_chain_report",
    ],
    "analitix.group_corporate": [
        "analitix.action_chain_report",
        "analitix.action_brand",
        "analitix.action_region",
    ],
    "analitix.group_security": [
        "analitix.action_watch_person",
        "analitix.action_watch_match",
    ],
}


@tagged("post_install", "-at_install")
class TestEveryScreenOpens(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.users = {}
        for group in SCREENS:
            cls.users[group] = cls.env["res.users"].with_context(
                no_reset_password=True).create({
                    "name": "Screen %s" % group,
                    "login": "screen_%s" % group.replace(".", "_"),
                    "group_ids": [
                        (4, cls.env.ref("base.group_user").id),
                        (4, cls.env.ref(group).id),
                    ],
                })

    def _open(self, user, xmlid):
        """Do what the web client does, through the same entry point.

        ``_for_xml_id`` is what the client calls to load an action; reading the
        ``ir.actions.act_window`` record directly is not, and asserting on that
        would be testing a path no user ever takes.
        """
        action = self.env["ir.actions.actions"].with_user(user)._for_xml_id(xmlid)
        model = self.env[action["res_model"]].with_user(user)
        model.check_access("read")

        for mode in (action.get("view_mode") or "list").split(","):
            mode = mode.strip()
            if not mode:
                continue
            view = model.get_view(view_type=mode)
            # Read the field list off the PROCESSED arch, not off
            # ``view["models"]``: the arch is what the browser is actually
            # handed, with group-restricted nodes already removed. Using the
            # raw model list would flag fields this role never receives, and a
            # test that fails on something the user cannot see teaches nothing.
            names = {
                node.get("name")
                for node in etree.fromstring(view["arch"]).iter("field")
                if node.get("name")
            }
            for name in names:
                field = model._fields.get(name)
                if field and field.relational:
                    # The exact step that failed for real: the client resolves
                    # the comodel behind every relational field on the view.
                    self.env[field.comodel_name].with_user(user).check_access("read")
            model.search([], limit=5).read(
                [n for n in names if n in model._fields])

    def test_every_screen_opens_for_its_own_role(self):
        failures = []
        for group, xmlids in SCREENS.items():
            user = self.users[group]
            for xmlid in xmlids:
                try:
                    self._open(user, xmlid)
                except AccessError as error:
                    failures.append("%s / %s: %s" % (
                        group, xmlid, str(error).splitlines()[0]))
                except Exception as error:  # noqa: BLE001
                    failures.append("%s / %s: %r" % (group, xmlid, error))
        self.assertFalse(
            failures,
            "screens a role cannot open with only its own rights:\n  " +
            "\n  ".join(failures))

    def test_a_manager_can_configure_a_store_without_pos_rights(self):
        """The original bug, named.

        A shop's Analitix manager is very often not a Point of Sale user — the
        person who configures the cameras is not the person who runs the till.
        They must still be able to open their store and choose which registers
        feed its conversion rate.
        """
        manager = self.users["analitix.group_manager"]
        self.assertFalse(
            manager.has_group("point_of_sale.group_pos_user"),
            "the fixture accidentally granted POS rights, so this proves nothing")
        store = self.env["analitix.store"].with_user(manager).create({
            "name": "Screen test store", "code": "SCR",
            "company_id": self.env.company.id, "tz": "UTC",
        })
        # Reading the register field is what blew up in the browser.
        store.read(["name", "register_ids", "match_mode"])
        self.env["pos.config"].with_user(manager).check_access("read")

    def test_a_manager_can_enrol_staff_without_hr_rights(self):
        """Same trap, different screen: staff enrolment names an employee."""
        manager = self.users["analitix.group_manager"]
        self.assertFalse(manager.has_group("hr.group_hr_user"))
        self.env["hr.employee"].with_user(manager).check_access("read")

    def test_analitix_grants_read_only_into_other_apps(self):
        """The access added for the screens above must never let Analitix
        change another application's data."""
        manager = self.users["analitix.group_manager"]
        user = self.users["analitix.group_user"]
        for model, who in (("pos.config", manager), ("sale.order", manager),
                           ("pos.order", user), ("crm.lead", user),
                           ("hr.employee", user)):
            for operation in ("write", "create", "unlink"):
                with self.assertRaises(
                        AccessError,
                        msg="%s may %s %s" % (who.login, operation, model)):
                    self.env[model].with_user(who).check_access(operation)


@tagged("post_install", "-at_install")
class TestGroupedFiguresAreNotNonsense(TransactionCase):
    """A ratio must never be summed when rows are grouped.

    Grouping a week of daily conversion rates by region produced a group total
    of **750%**, because Odoo sums Floats by default and a percentage is not a
    quantity. The hourly views have declared ``aggregator="avg"`` since phase 1;
    the models added in phase 7 forgot, and nothing failed — the number was
    simply wrong on the screen a chain is sold on.

    So the rule is asserted directly rather than trusted to review: any field
    whose name says it is a rate, an average or a per-something either averages
    or does not aggregate at all.
    """

    #: Name fragments that mean "this is a ratio, not a quantity".
    RATIO_HINTS = ("_rate", "rate_", "atv", "upt", "_per_", "_vs_", "average")

    def test_no_ratio_field_is_summed(self):
        offenders = []
        for name, model in self.env.registry.items():
            if not name.startswith("analitix."):
                continue
            records = self.env[name]
            if not records._auto and not records._table:
                continue
            for field_name, field in records._fields.items():
                if field.type not in ("float", "monetary"):
                    continue
                if not any(hint in field_name for hint in self.RATIO_HINTS):
                    continue
                if field.aggregator in ("avg", None, False):
                    continue
                offenders.append("%s.%s aggregates as %r" % (
                    name, field_name, field.aggregator))
        self.assertFalse(
            offenders,
            "ratios that would be summed into a meaningless group total:\n  " +
            "\n  ".join(offenders))


@tagged("post_install", "-at_install")
class TestSampleDataDoesNotCrashOnHourlyViews(TransactionCase):
    """Una vista agrupada por HORA no puede pedir datos de ejemplo.

    Odoo genera datos falsos cuando una vista no tiene registros, y su
    formateador solo conoce day/week/month/quarter/year — no *hour*. Con
    ``sample="1"`` y ``interval="hour"``, una vista vacía revienta en el
    navegador con «Cannot read properties of undefined (reading 'length')»,
    que es exactamente lo que ve una tienda recién instalada antes de su
    primer cruce.

    Se detectó en la demo de retail. Se prueba aquí y no a mano porque el
    atributo es fácil de volver a poner sin saber lo que cuesta.
    """

    def test_no_hourly_view_asks_for_sample_data(self):
        offenders = []
        views = self.env["ir.ui.view"].search([
            ("type", "in", ("graph", "pivot")),
            ("model", "like", "analitix."),
        ])
        for view in views:
            arch = etree.fromstring(view.arch)
            if arch.get("sample") not in ("1", "true", "True"):
                continue
            if arch.xpath('.//field[@interval="hour"]'):
                offenders.append("%s (%s)" % (view.xml_id or view.name, view.model))
        self.assertFalse(
            offenders,
            "Estas vistas agrupan por hora y piden datos de ejemplo; en una "
            "base vacía truenan en el navegador: %s" % ", ".join(offenders))
