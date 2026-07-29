import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class RepairOrder(models.Model):
    _inherit = "repair.order"

    xb_wa_reminder_stage = fields.Integer(
        string="Last reminder (days)",
        default=0,
        copy=False,
        help="Highest reminder threshold already sent, so the same nudge is "
        "never sent twice.",
    )
    xb_wa_unclaimed = fields.Boolean(
        string="Unclaimed",
        copy=False,
        help="Ready for longer than the shop's limit and still not picked up.",
    )

    def _xb_wa_send(self, template):
        """Send one template to this order's customer.

        Failures are logged and posted on the record, never raised: a phone
        that no longer exists must not block the counter from finishing a
        delivery.
        """
        self.ensure_one()
        if not template:
            # The shop asked for the customer to be told. Not having got a
            # template approved by Meta yet is the shop's problem, not the
            # customer's: write to them instead of staying silent.
            return self._xb_notify_by_email(
                reason=_("no WhatsApp template is configured")
            )
        # Odoo 19 dropped res.partner.mobile: there is only `phone` now.
        if not self.partner_id.phone:
            self.message_post(
                body=_("No phone number on file, WhatsApp not sent."),
                message_type="comment",
            )
            return self._xb_notify_by_email(reason=_("no phone number on file"))
        try:
            composer = self.env["whatsapp.composer"].with_context(
                active_model="repair.order", active_ids=self.ids
            ).create({
                "res_model": "repair.order",
                "res_ids": str(self.id),
                "wa_template_id": template.id,
            })
            composer._send_whatsapp_template(force_send_by_cron=True)
            return True
        except Exception as error:  # noqa: BLE001 - never break the flow
            _logger.warning(
                "Jewelry WhatsApp failed for %s: %s", self.name, error
            )
            self.message_post(
                body=_("WhatsApp could not be sent: %(err)s", err=str(error)[:200]),
                message_type="comment",
            )
            return self._xb_notify_by_email(reason=str(error)[:120])

    def _xb_notify_by_email(self, reason=""):
        """Fall back to email when WhatsApp is not an option.

        The customer has just handed over gold; being told nothing because a
        phone number is missing is not acceptable. Email is worse than
        WhatsApp, and better than silence.
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company.xb_email_fallback:
            return False
        if not self.partner_id.email:
            self.message_post(
                body=_("No phone and no email on file: the customer was not "
                       "notified. Tell them yourself."),
                message_type="comment",
            )
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=_("Customer could not be notified"),
                note=_("Neither WhatsApp nor email was possible for %(ref)s.",
                       ref=self.name),
                user_id=self.user_id.id or self.env.uid,
            )
            return False
        try:
            piece = self.jewelry_piece_id
            body = _(
                "<p>Hello %(name)s,</p>"
                "<p>We have your %(piece)s in our care under reference "
                "<strong>%(ref)s</strong>. We will let you know as soon as it "
                "is ready.</p>",
                name=self.partner_id.name,
                piece=piece.description or _("piece"),
                ref=self.name,
            )
            self.message_post(
                body=body,
                subject=_("%(company)s - piece received (%(ref)s)",
                          company=company.name, ref=self.name),
                partner_ids=self.partner_id.ids,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
            if reason:
                self.message_post(
                    body=_("Notified by email instead of WhatsApp: %(why)s.",
                           why=reason),
                    message_type="comment",
                )
            return True
        except Exception as error:  # noqa: BLE001 - never break the counter
            _logger.warning("Jewelry email fallback failed for %s: %s",
                            self.name, error)
            return False

    def action_qc_pass(self):
        res = super().action_qc_pass()
        for repair in self:
            company = repair.company_id or self.env.company
            if company.xb_wa_notify_ready:
                repair._xb_wa_send(company.xb_wa_template_ready_id)
        return res

    def xb_pos_receive_piece_hook(self):
        """Called after a piece is taken in, when the shop wants a receipt
        message on the customer's phone."""
        for repair in self:
            company = repair.company_id or self.env.company
            if company.xb_wa_notify_received:
                repair._xb_wa_send(company.xb_wa_template_received_id)

    def action_xb_wa_send_ready(self):
        for repair in self:
            company = repair.company_id or self.env.company
            if not company.xb_wa_template_ready_id:
                raise UserError(
                    _("Pick the 'piece ready' template in the settings first.")
                )
            repair._xb_wa_send(company.xb_wa_template_ready_id)
        return True

    def action_xb_wa_send_quote(self):
        for repair in self:
            company = repair.company_id or self.env.company
            if not company.xb_wa_template_quote_id:
                raise UserError(
                    _("Pick the 'quote to authorize' template in the settings first.")
                )
            repair._xb_wa_send(company.xb_wa_template_quote_id)
        return True

    @api.model
    def _cron_xb_jewelry_pickup_reminders(self):
        """Chase pieces that are ready and still sitting in the safe."""
        today = fields.Date.context_today(self)
        pending = self.search(
            [("state", "=", "done"), ("jewelry_piece_id", "!=", False)]
        )
        for repair in pending:
            company = repair.company_id or self.env.company
            thresholds = company._xb_reminder_thresholds()
            if not repair.qc_date:
                continue
            waiting = (today - repair.qc_date.date()).days

            # Unclaimed is a separate matter from a reminder: nobody is
            # nudged, the shop is warned, because what happens next is a
            # decision with legal weight.
            if (
                company.xb_unclaimed_days
                and waiting >= company.xb_unclaimed_days
                and not repair.xb_wa_unclaimed
            ):
                repair.xb_wa_unclaimed = True
                repair.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=_("Unclaimed piece"),
                    note=_(
                        "%(days)s days ready and not picked up. Decide what to "
                        "do following the terms the customer signed.",
                        days=waiting,
                    ),
                    user_id=repair.user_id.id or self.env.uid,
                )

            due = [d for d in thresholds if d <= waiting
                   and d > repair.xb_wa_reminder_stage]
            if not due or not company.xb_wa_template_reminder_id:
                continue
            if repair._xb_wa_send(company.xb_wa_template_reminder_id):
                repair.xb_wa_reminder_stage = max(due)
        return True
