# -*- coding: utf-8 -*-
"""The manuals, served in the reader's own language.

The documents themselves are plain static HTML rather than QWeb templates, for
two reasons that both matter:

* **They are written, not translated.** A manual run through a msgid dictionary
  reads like one. Each language is authored on its own, so the Spanish can say
  "una venta que se fue caminando" instead of a literal rendering of "a sale
  that walked out".
* **They stay out of the ``.pot``.** Four documents of this length would add
  several thousand msgids to the module's translation file and bury the strings
  that genuinely need translating — the field labels and help texts an
  implementer reads inside the UI.

All this controller does is choose the file. It is a redirect rather than a
render so the browser can cache the document and the user can bookmark it.
"""
from odoo import http
from odoo.http import request

#: kind -> basename. Anything not in here 404s rather than reaching the
#: filesystem: a route that interpolates a user-supplied name into a path is
#: how a documentation link turns into a file-disclosure bug.
DOCUMENTS = {
    "user": "user",
    "implementer": "implementer",
}


class AnalitixManual(http.Controller):

    @http.route("/analitix/manual/<string:kind>", type="http", auth="user",
                website=False)
    def manual(self, kind, lang=None, **kwargs):
        """Redirect to the manual for ``kind`` in the reader's language.

        ``auth="user"`` because these are internal documents: they describe a
        customer's floor plan, their thresholds and their watch-list policy.
        """
        basename = DOCUMENTS.get(kind)
        if not basename:
            return request.not_found()

        # An explicit ?lang= wins, so somebody can send a colleague the English
        # version without changing their own Odoo language.
        code = lang or request.env.user.lang or "en_US"
        suffix = "es" if code.lower().startswith("es") else "en"
        return request.redirect(
            "/analitix/static/manual/%s_%s.html" % (basename, suffix),
            local=True)
