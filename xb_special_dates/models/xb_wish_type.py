# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class XbWishType(models.Model):
    _name = "xb.wish.type"
    _description = "Special Date Type"
    _order = "name"

    # ------------------------------------------------------------------
    # There used to be a ``_register_hook`` here that re-imported both .po
    # files with overwrite=True from a BRAND NEW CURSOR
    # (``self.env.registry.cursor()``).
    #
    # That hangs any ``-i`` or ``-u`` of ANY module in the database, and every
    # live worker with it: the upgrade transaction already holds the locks on
    # ir_model and on every table with translatable fields, the new cursor asks
    # for those very rows, and neither side can move. PostgreSQL does not break
    # the tie because it sees no cycle — one side is blocked in Python, not in
    # SQL. It froze a production database for twenty minutes.
    #
    # The ``except Exception: pass`` around it guarded against the reload
    # FAILING, not against it HANGING, which is what it actually did.
    #
    # The reload still happens, just from where it cannot deadlock: the
    # manifest's ``post_init_hook`` on install, and the ``<function>`` in
    # data/load_translations.xml on every upgrade. Both run inside the cursor
    # that is already open, so there are never two connections to trip over
    # each other.
    # ------------------------------------------------------------------
    @api.model
    def _reload_bundled_translations(self):
        """Reload the module's bundled .po files.

        Called by data/load_translations.xml on every upgrade."""
        from odoo.addons.xb_special_dates import _load_translations_overwrite
        _load_translations_overwrite(self.env)
        return True

    name = fields.Char(string="Name", required=True, translate=True)
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    period_type = fields.Selection(
        selection=[
            ("day", "Day of the Week"),
            ("no_of_day", "Every N Days"),
            ("year", "Every Year (anniversary)"),
        ],
        default="year",
        string="Period",
        required=True,
    )
    day_type = fields.Selection(
        selection=[
            ("0", "Monday"),
            ("1", "Tuesday"),
            ("2", "Wednesday"),
            ("3", "Thursday"),
            ("4", "Friday"),
            ("5", "Saturday"),
            ("6", "Sunday"),
        ],
        default="0",
        string="Default Day",
    )
    no_of_day = fields.Integer(string="Default Number of Days")
    date = fields.Date(string="Default Date")
    color = fields.Integer(string="Color Index")
    show_in_pos = fields.Boolean(
        string="Show Popup in Point of Sale",
        default=True,
        help="When enabled, this reminder type can trigger a celebratory "
             "popup in the Point of Sale on its date. Uncheck to silence "
             "this type from the POS without disabling it for emails, SMS, "
             "or auto-activities.",
    )
    icon = fields.Selection(
        selection=[
            ("🎉", "🎉 Celebration"),
            ("🎂", "🎂 Birthday"),
            ("🎁", "🎁 Gift"),
            ("💍", "💍 Wedding / Engagement"),
            ("💕", "💕 Love / Anniversary"),
            ("❤️", "❤️ Heart"),
            ("🌹", "🌹 Rose"),
            ("🥂", "🥂 Cheers"),
            ("🍾", "🍾 Champagne"),
            ("🎊", "🎊 Confetti"),
            ("🎈", "🎈 Balloon"),
            ("🌟", "🌟 Star"),
            ("⭐", "⭐ Star (yellow)"),
            ("✨", "✨ Sparkles"),
            ("🏆", "🏆 Trophy"),
            ("🥇", "🥇 Gold Medal"),
            ("👶", "👶 Baby"),
            ("👰", "👰 Bride"),
            ("🤵", "🤵 Groom"),
            ("🎓", "🎓 Graduation"),
            ("📅", "📅 Calendar"),
            ("🗓️", "🗓️ Date"),
            ("☀️", "☀️ Sun"),
            ("🌙", "🌙 Moon"),
            ("🎄", "🎄 Christmas"),
            ("🦃", "🦃 Thanksgiving"),
            ("👑", "👑 Crown"),
            ("💎", "💎 Diamond"),
            ("🔔", "🔔 Bell"),
            ("⏰", "⏰ Reminder"),
        ],
        string="Icon",
        default="🎉",
        required=True,
        help="Emoji shown in the POS popup. Choose from the list.",
    )

    xb_pos_auto_capture = fields.Boolean(
        string="Capture at Point of Sale",
        default=False,
        help="When enabled, this Reminder Type can be captured at the "
             "Point of Sale: when a cashier sells a product whose POS "
             "category triggers this type, a popup asks to register the "
             "special date for the customer. Independent of "
             "'Show Popup in Point of Sale' (which controls the day-of "
             "celebratory popup).",
    )

    schedule_ids = fields.One2many(
        comodel_name="xb.wish.schedule",
        inverse_name="wish_type_id",
        string="Communications",
        copy=True,
    )
    schedule_count = fields.Integer(
        string="# Schedules", compute="_compute_schedule_count",
    )

    activity_ids = fields.One2many(
        comodel_name="xb.wish.activity",
        inverse_name="wish_type_id",
        string="Auto-Activities",
        copy=True,
        help="Activities (Call, Email, To-Do, ...) automatically "
             "created on the customer's record when this date arrives.",
    )
    activity_count = fields.Integer(
        string="# Activities", compute="_compute_activity_count",
    )

    @api.depends("schedule_ids")
    def _compute_schedule_count(self):
        for rec in self:
            rec.schedule_count = len(rec.schedule_ids)

    @api.depends("activity_ids")
    def _compute_activity_count(self):
        for rec in self:
            rec.activity_count = len(rec.activity_ids)

    @api.constrains("no_of_day")
    def _check_no_of_day(self):
        for rec in self:
            if rec.no_of_day and rec.no_of_day <= 0:
                raise ValidationError(
                    _("Number of days must be a positive integer.")
                )

    # ------------------------------------------------------------------
    # Manual trigger - useful for testing without waiting for the cron
    # ------------------------------------------------------------------
    def action_run_now(self):
        """Force the daily reminder cron to run now. Sends emails/SMS
        and creates activities for any reminder due today. Visible to
        managers as a button on the Reminder Type form."""
        self.env["xb.wish.reminders"].sudo().cron_send_date_reminders()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Special Dates"),
                "message": _("Daily reminders processed. Check the chatter "
                             "of due reminders to see what was sent."),
                "type": "success",
                "sticky": False,
            },
        }
