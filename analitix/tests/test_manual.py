# -*- coding: utf-8 -*-
"""Phase 6: the manuals reach the reader, in their own language.

Documentation that ships inside the product only helps if the link works, and a
broken help link is the kind of thing nobody notices until a customer is already
stuck. So the route is tested like any other endpoint.
"""
import os

from odoo.tests.common import HttpCase, TransactionCase, tagged

MANUAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "static", "manual")


@tagged("post_install", "-at_install")
class TestManualFiles(TransactionCase):

    def test_every_document_exists_in_both_languages(self):
        """The controller can only redirect to files that are actually there."""
        from odoo.addons.analitix.controllers.manual import DOCUMENTS
        for basename in DOCUMENTS.values():
            for suffix in ("es", "en"):
                path = os.path.join(MANUAL_DIR, "%s_%s.html" % (basename, suffix))
                self.assertTrue(os.path.exists(path),
                                "the manual %s is missing" % path)
                self.assertGreater(
                    os.path.getsize(path), 4000,
                    "%s looks like a stub rather than a manual" % path)

    def test_the_menu_actions_point_at_the_route(self):
        for xmlid in ("analitix.action_manual_user",
                      "analitix.action_manual_implementer"):
            action = self.env.ref(xmlid)
            self.assertTrue(action.url.startswith("/analitix/manual/"))
            self.assertEqual(action.target, "new")


@tagged("post_install", "-at_install")
class TestManualRoute(HttpCase):

    def test_spanish_user_gets_the_spanish_manual(self):
        self.authenticate("admin", "admin")
        user = self.env.ref("base.user_admin")
        lang = self.env["res.lang"].with_context(active_test=False).search(
            [("code", "=like", "es%")], limit=1)
        if not lang:
            self.skipTest("no Spanish language available in this database")
        lang.active = True
        user.lang = lang.code
        response = self.url_open("/analitix/manual/user", allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("user_es.html", response.headers.get("Location", ""))

    def test_an_english_user_gets_the_english_manual(self):
        self.authenticate("admin", "admin")
        self.env.ref("base.user_admin").lang = "en_US"
        response = self.url_open("/analitix/manual/user", allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("user_en.html", response.headers.get("Location", ""))

    def test_an_explicit_language_wins(self):
        """So somebody can send a colleague the English one without changing
        their own Odoo language."""
        self.authenticate("admin", "admin")
        response = self.url_open(
            "/analitix/manual/implementer?lang=es_MX", allow_redirects=False)
        self.assertIn("implementer_es.html", response.headers.get("Location", ""))

    def test_an_unknown_document_is_not_found(self):
        """The route must never interpolate a user-supplied name into a path —
        that is how a documentation link becomes a file-disclosure bug."""
        self.authenticate("admin", "admin")
        response = self.url_open(
            "/analitix/manual/..%2f..%2fodoo.conf", allow_redirects=False)
        self.assertIn(response.status_code, (400, 404))

    def test_the_manual_itself_is_served(self):
        self.authenticate("admin", "admin")
        response = self.url_open("/analitix/static/manual/user_en.html")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Analitix", response.text)
