# -*- coding: utf-8 -*-
import logging

from urllib.parse import urlparse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

MODE_PARAM = "xb_calendar_domain.mode"
URL_PARAM = "xb_calendar_domain.url"


def normalize_base_url(url):
    """Return ``url`` as a usable base URL, or an empty string.

    Anything that is not an absolute http(s) address is rejected rather than
    patched up: a half-valid domain inside a meeting invitation is worse than
    falling back to the base URL Odoo would have used anyway.
    """
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return url


class ResCompany(models.Model):
    _inherit = "res.company"

    xb_calendar_link_url = fields.Char(
        string="Meeting Links Domain",
        help="Domain used in the meeting links of this company: the videocall "
             "link, the invitation, reminder and update emails, and the "
             "accept / decline / view pages.\n"
             "Only used when the calendar setting is set to one domain per "
             "company. Leave it empty to fall back to the general domain.",
    )

    xb_calendar_link_title = fields.Char(
        string="Videocall Page Title",
        help="Name announced by the videocall page, which is what WhatsApp, "
             "Telegram or Slack show when the link is pasted into a chat, and "
             "what the browser tab reads.\n"
             "Leave it empty to use the name of the company.",
    )

    def _register_hook(self):
        """Ship the manual once the whole registry is up.

        Not ``post_init_hook`` and not a migration script: both run while this
        module is loading, and ``knowledge`` loads after it, so the article
        would be skipped in silence. See ``manual.install_manual``.
        """
        res = super()._register_hook()
        try:
            from ..manual import install_manual
            install_manual(self.env)
        except Exception:  # noqa: BLE001
            # A manual is never worth blocking a server start for.
            _logger.exception("xb_calendar_domain: could not install the manual")
        return res

    @api.constrains("xb_calendar_link_url")
    def _check_xb_calendar_link_url(self):
        for company in self:
            raw = (company.xb_calendar_link_url or "").strip()
            if raw and not normalize_base_url(raw):
                raise ValidationError(_(
                    "%(url)s is not a valid meeting links domain. Write the "
                    "full address, for example https://meet.mycompany.com",
                    url=raw,
                ))

    def _xb_calendar_base_url(self):
        """Domain configured for calendar links, or '' to keep Odoo's own.

        Returning an empty string is meaningful: every caller falls back to
        ``super().get_base_url()``, so a missing or malformed setting leaves
        the database behaving exactly as it did before installing the module.
        """
        icp = self.env["ir.config_parameter"].sudo()
        mode = icp.get_param(MODE_PARAM) or "default"
        if mode not in ("fixed", "company"):
            return ""
        general = normalize_base_url(icp.get_param(URL_PARAM))
        if mode == "fixed":
            return general
        company = self[:1] or self.env.company
        return normalize_base_url(company.sudo().xb_calendar_link_url) or general

    def _xb_calendar_public_title(self):
        """Name the videocall page announces, or '' to keep Odoo's own.

        Inert in default mode like everything else here, so switching back —
        or uninstalling — leaves the page exactly as Odoo renders it.
        """
        icp = self.env["ir.config_parameter"].sudo()
        mode = icp.get_param(MODE_PARAM) or "default"
        if mode not in ("fixed", "company"):
            return ""
        company = (self[:1] or self.env.company).sudo()
        return (company.xb_calendar_link_title or "").strip() or company.name
