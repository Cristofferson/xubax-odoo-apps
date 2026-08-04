# -*- coding: utf-8 -*-
"""Activating a shop: the one place the commercial terms touch the software.

The rest of this addon deliberately does not meter anything. A store's plan is
a configuration control, and no billing problem can switch a running camera
off — that promise is worth keeping, because the failure mode it prevents (a
customer's shop goes blind because of an invoice on *our* side) is far more
expensive than the one it allows.

But a promise that only protects the customer is only half a design. Nothing
stopped a customer from running twenty shops and paying for three, and nothing
even told us it was happening.

So the gate sits at the one moment where it is honest and cheap:

**A device key is only issued for a store that has been activated.**

Not at ingest. A store already collecting keeps collecting, forever, whatever
happens to the invoice — the camera never goes dark. What needs a code is
bringing a *new* shop online, which is also the moment we are physically in the
shop mounting and calibrating a camera. The gate follows the work that already
exists rather than inventing a new one.

The first store is free
-----------------------
A database with no activated store can activate one itself. That is not a
loophole, it is the trial the listing already promises: install with demo data,
run the agent in ``demo`` mode, prove the whole chain end to end before buying
a camera. Shop number two is where the conversation happens.

How the code works
------------------
An Ed25519 signature over ``<database uuid>:<store code>``. Two consequences
worth stating:

* a code issued for one shop cannot be moved to another shop, and
* a code cannot be moved to another database — including a copy of this one.

Only the public key ships. The signing key never leaves XUBAX, so a customer
cannot mint their own, and neither can anybody who reads this source. What they
*can* do is patch this file out, and that is fine: this is friction and an
audit trail, not DRM. It turns over-activation from something that happens by
accident into something somebody has to decide to do — and the reconciliation
report on our side sees the result either way.
"""
import base64
import logging

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: XUBAX's activation public key. Verifying only — the signing half is not here
#: and is not in this repository.
ACTIVATION_PUBLIC_KEY = "Qhzqcny9cgk+GKs+fp9zfYQAN+Ydgf+O7ZF/mF419kE="

#: What a self-activated first store carries instead of a signature.
TRIAL_TOKEN = "TRIAL"


class AnalitixStoreActivation(models.Model):
    _inherit = "analitix.store"

    activated = fields.Boolean(
        string="Activated", default=False, copy=False, readonly=True,
        tracking=True,
        help="A store must be activated before its cameras can be given a key. "
             "Activation is permanent: it is never withdrawn by a billing "
             "problem, and a store already collecting data keeps collecting.")
    activation_token = fields.Char(
        string="Activation Code", copy=False, readonly=True, groups="analitix.group_manager",
        help="The signed code this store was activated with, kept for the "
             "record. TRIAL means it was the first store in this database and "
             "activated itself.")
    activation_date = fields.Datetime(string="Activated On", copy=False, readonly=True)
    activation_code_input = fields.Char(
        string="Paste the code here", copy=False,
        help="The code XUBAX sends back. It is checked when you press "
             "Activate, and cleared afterwards.")
    activation_request = fields.Char(
        string="Activation Request", compute="_compute_activation_request",
        help="Send this line to XUBAX to get the code for this store. It "
             "identifies the database and the shop and nothing else.")

    @api.depends("code")
    def _compute_activation_request(self):
        uuid = self.env["ir.config_parameter"].sudo().get_param(
            "database.uuid", default="")
        for store in self:
            store.activation_request = (
                "%s:%s" % (uuid, store.code) if store.code else False)

    # ------------------------------------------------------------------
    @api.model
    def _activation_public_key(self):
        return ed25519.Ed25519PublicKey.from_public_bytes(
            base64.b64decode(ACTIVATION_PUBLIC_KEY))

    def _activation_payload(self):
        self.ensure_one()
        if not self.code:
            raise UserError(_(
                "This store has no code yet, and the activation code is tied "
                "to it. Give the shop a code first."))
        uuid = self.env["ir.config_parameter"].sudo().get_param(
            "database.uuid", default="")
        return ("%s:%s" % (uuid, self.code)).encode()

    def _verify_activation(self, code):
        """True when *code* is XUBAX's signature for exactly this store."""
        self.ensure_one()
        try:
            signature = base64.b64decode((code or "").strip(), validate=True)
        except Exception:  # noqa: BLE001 — any malformed input is simply invalid
            return False
        try:
            self._activation_public_key().verify(
                signature, self._activation_payload())
        except InvalidSignature:
            return False
        except Exception:  # noqa: BLE001
            _logger.exception("Activation check failed for store %s", self.code)
            return False
        return True

    # ------------------------------------------------------------------
    def action_activate_store(self):
        """Activate this store with a code issued by XUBAX.

        Not ``action_activate``: that name already belongs to the
        subscription, and a shop being commissioned and a subscription
        being switched on are different events on purpose.
        """
        self.ensure_one()
        code = (self.activation_code_input or "").strip()
        if not code:
            raise UserError(_("Paste the activation code first."))
        if not self._verify_activation(code):
            raise UserError(_(
                "That code is not valid for this shop.\n\nA code is tied to "
                "one shop in one database, so a code issued for another "
                "branch — or for a copy of this database — will not work "
                "here. Check that the store's code has not changed since you "
                "asked for it."))
        self._mark_activated(code)
        self.sudo().write({"activation_code_input": False})
        return True

    def action_activate_trial(self):
        """Let the first store in a database activate itself.

        The listing promises the whole chain can be proven before any hardware
        is bought; refusing a key to the very first store would make that
        promise false. From the second shop on, activation goes through us.
        """
        self.ensure_one()
        others = self.sudo().search_count([
            ("activated", "=", True), ("id", "!=", self.id)])
        if others:
            raise UserError(_(
                "This database already has an activated shop, so this one "
                "needs an activation code from XUBAX.\n\nSend them this "
                "line:\n\n%(request)s", request=self.activation_request or ""))
        self._mark_activated(TRIAL_TOKEN)
        return True

    def _mark_activated(self, token):
        self.ensure_one()
        self.sudo().write({
            "activated": True,
            "activation_token": token,
            "activation_date": fields.Datetime.now(),
        })
        self.message_post(body=_(
            "Store activated by %(user)s (%(kind)s).",
            user=self.env.user.display_name,
            kind=_("trial") if token == TRIAL_TOKEN else _("code")))
        self.env["analitix.audit.log"].sudo().log(
            action="store_activate", model=self._name, res_id=self.id,
            store=self, note=_("Activated with %s",
                               "TRIAL" if token == TRIAL_TOKEN else "code"))
        return True

    def _may_issue_key(self):
        """Soft form of :meth:`_ensure_activated`, for the automatic path.

        A device is created in the middle of the setup wizard, along with the
        shop and its doors. Blowing up there would leave the person half way
        through a form with nothing to show for it, so the automatic path just
        declines to mint a key and says nothing: the shop exists, its cameras
        exist, and the moment it is activated a key is one button away.
        """
        self.ensure_one()
        if self.activated:
            return True
        if not self.sudo().search_count([("activated", "=", True)]):
            self._mark_activated(TRIAL_TOKEN)
            return True
        return False

    def _ensure_activated(self):
        """Raise unless this store may be given camera keys.

        A database whose first shop is still unactivated activates it here,
        silently. That is the trial, and making it silent matters: somebody
        evaluating the product should reach a working chain without ever
        meeting this mechanism. The second shop is where it appears.
        """
        self.ensure_one()
        if self.activated:
            return True
        if not self.sudo().search_count([("activated", "=", True)]):
            self._mark_activated(TRIAL_TOKEN)
            return True
        raise UserError(_(
            "“%(store)s” is not activated yet, so its cameras cannot be given "
            "a key.\n\nSend this line to XUBAX and they will send back the "
            "activation code:\n\n%(request)s\n\nNothing already running is "
            "affected by this — activation is only needed to bring a new shop "
            "online.", store=self.display_name,
            request=self.activation_request or _("(give the shop a code first)")))
