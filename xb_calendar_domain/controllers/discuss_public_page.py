# -*- coding: utf-8 -*-
from odoo.addons.mail.controllers.discuss.public_page import PublicPageController


class XbCalendarPublicPage(PublicPageController):
    def _response_discuss_public_template(self, store, channel):
        """Announce the company instead of a bare "Odoo".

        The videocall page is the one a messaging app reads when the link is
        pasted into a chat: WhatsApp, Telegram and Slack all build their
        preview from its ``<title>``, and Odoo leaves it at the hardcoded
        default. ``request.render`` is lazy — the response carries the template
        and its context and is only rendered at the end of the dispatch — so
        the title can be filled in here without copying the body of the
        original controller, which keeps working after an Odoo update.
        """
        response = super()._response_discuss_public_template(store, channel)
        qcontext = getattr(response, "qcontext", None)
        if qcontext is None or qcontext.get("title"):
            return response
        # An empty company means the channel is not a meeting: hands off.
        company = channel.sudo()._xb_calendar_company()
        title = company._xb_calendar_public_title() if company else ""
        if title:
            qcontext["title"] = title
        return response
