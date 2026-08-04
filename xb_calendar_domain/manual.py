# -*- coding: utf-8 -*-
"""Administrator manual, shipped with the module as a Knowledge article.

Why it lives in Python instead of a data XML: the article is only created
where Knowledge is installed (it is an Enterprise app), and making the module
depend on it would lock every Community buyer out. A hook can ask.

Why the body is built from _() calls instead of a static HTML file: the
article body is a plain html field, not a translatable one, so the language
has to be chosen when the record is written. Building it from translated
strings gives one source and any language the .po covers -- and the
screenshots follow, since they ship in an ``es`` and an ``en`` set.
"""
import hashlib
import logging

from odoo import SUPERUSER_ID
from odoo.tools.translate import _, code_translations

_logger = logging.getLogger(__name__)

ARTICLE_XMLID = 'xb_calendar_domain.article_meeting_links_manual'
CHECKSUM_PARAM = 'xb_calendar_domain.manual_checksum'
STAMP_PARAM = 'xb_calendar_domain.manual_stamp'
IMG_BASE = '/xb_calendar_domain/static/src/img/manual'


def _img(folder, name, alt):
    return (
        '<p><img src="%s/%s/%s.png" alt="%s" class="img-fluid" '
        'style="width:100%%;max-width:900px;border-radius:8px;"></p>'
        % (IMG_BASE, folder, name, alt)
    )


def _h(text):
    return '<h2>%s</h2>' % text


def _p(text):
    return '<p><span style="font-size: 14px;">%s</span></p>' % text


def _note(text):
    return '<blockquote>%s</blockquote>' % _p(text)


def _rows(rows):
    return ''.join(
        '<tr>%s</tr>' % ''.join('<td>%s</td>' % c for c in row) for row in rows
    )


def _table(head, rows):
    return (
        '<table class="table table-bordered"><tbody><tr>%s</tr>%s</tbody></table>'
        % (''.join('<td><strong>%s</strong></td>' % h for h in head), _rows(rows))
    )


def _saved_checksum(article):
    """Checksum of the manual **as Odoo stored it**.

    ``knowledge.article.body`` is an html field, so what comes back from the
    database is not what was handed to ``write()``: Odoo sanitises it on the
    way in -- it escapes ``>`` into ``&gt;`` and stamps its own attributes on
    the blockquotes. Hashing the HTML this module generated, as version
    19.0.1.2.0 and earlier did, therefore never matched on the next boot: an
    untouched article looked edited and the manual froze for good.

    The ``v2:`` prefix marks the values written by this way of computing it,
    which is what tells an old checksum apart from a real local edit.
    """
    article.flush_recordset(['body'])
    article.invalidate_recordset(['body'])
    return 'v2:%s' % hashlib.sha256((article.body or '').encode()).hexdigest()


def _legacy_checksum_of_ours(previous, article):
    """Was that stale checksum written by an old version, on an untouched article?

    An unprefixed checksum comes from a version that hashed the wrong string,
    so its mismatch means nothing and cannot be read as a local edit. Who
    wrote the article last is the honest signal left: this module always
    writes it as the superuser, so anything else is a person.
    """
    return not previous.startswith('v2:') and article.write_uid.id == SUPERUSER_ID


def build_body(env):
    """Return the manual as HTML, in the language of ``env``."""
    lang = env.context.get('lang') or 'en_US'
    # _() reads the language off the CALLING FRAME (tools.translate._get_lang):
    # a local named `context` carrying a lang is the first thing it looks for.
    context = {'lang': lang}  # noqa: F841
    folder = 'es' if lang.startswith('es') else 'en'
    b = '<strong>%s</strong>'
    out = []

    out.append(_p(_(
        "Odoo builds every link of a meeting from one system-wide address, the "
        "base URL. This module gives meeting links a domain of their own, "
        "without touching that parameter -- so the portal, your website links "
        "and any custom development keep working exactly as before.")))

    out.append(_h(_("What it changes")))
    out.append(_p(_("Every link that points back at a meeting, not only the videocall:")))
    out.append(
        '<ul>'
        + '<li>%s</li>' % _p(_("The videocall link of the meeting (Odoo Discuss)."))
        + '<li>%s</li>' % _p(_("The invitation email, and its Accept, Decline and View buttons."))
        + '<li>%s</li>' % _p(_("The reminder email sent before the meeting."))
        + '<li>%s</li>' % _p(_("The date change, update and cancellation emails."))
        + '<li>%s</li>' % _p(_("The portal pages those buttons open."))
        + '<li>%s</li>' % _p(_("The name the videocall page announces, which is what a messaging app shows when the link is pasted into a chat."))
        + '</ul>')

    out.append(_h(_("Where it is configured")))
    out.append(_p(_(
        "%(menu)s. The section appears inside the Calendar settings, next to "
        "the Outlook and Google options.",
        menu=b % _("Settings > Calendar > Meeting Links"))))
    out.append(_img(folder, '01_ajustes', _("The Meeting Links section in the Calendar settings")))

    out.append(_h(_("The three options")))
    out.append(_table(
        [_("Option"), _("What it does"), _("When to use it")],
        [
            [_("Odoo default (system base URL)"),
             _("Nothing changes. The module is inert."),
             _("To go back, or before you have decided on a domain.")],
            [_("One domain for every meeting"),
             _("Every meeting in the database uses the domain you type."),
             _("One company, or one brand in front of customers.")],
            [_("One domain per company"),
             _("Each meeting carries the brand it goes out under, and follows its domain."),
             _("Several companies or brands in the same database.")],
        ]))

    out.append(_h(_("One domain for every meeting")))
    out.append(_p(_(
        "Pick the option and write the full address, for example "
        "%(url)s. Then press Save.", url=b % 'https://meet.mycompany.com')))
    out.append(_img(folder, '02_bloque', _("One domain for every meeting")))
    out.append(_note(_(
        "The domain has to be served by this same Odoo. The module decides "
        "which name is written into the link; it does not publish a new site, "
        "nor set up DNS or a certificate. If the address is empty or is not a "
        "valid http(s) address, it is ignored and the meeting falls back to "
        "the address Odoo would have used on its own.")))

    out.append(_h(_("One domain per company")))
    out.append(_p(_(
        "Each company gets its own address. The one at the top is the general "
        "fallback: companies left empty use it.")))
    out.append(_img(folder, '03_por_compania', _("One domain per company")))
    out.append(_p(_(
        "The field also lives on the company itself, right under its website, "
        "which is handier when there are several: %(menu)s.",
        menu=b % _("Settings > Users & Companies > Companies"))))
    out.append(_img(folder, '05_compania', _("The field on the company form")))
    out.append(_h(_("The brand of each meeting")))
    out.append(_p(_(
        "With one domain per company, every meeting carries the brand it goes "
        "out under, right under its video link. That company decides two "
        "things: the domain written into the link and the name the videocall "
        "page announces.")))
    out.append(_img(folder, '06_marca_reunion', _("The brand of a meeting")))
    out.append(_p(_(
        "A new meeting starts with the company selected in the top bar, which "
        "is the one Odoo builds the link with while the meeting is still "
        "unsaved: the link you are shown before saving is the one that gets "
        "saved. To send a single meeting out under another brand, change this "
        "field -- there is no need to change the Organiser, nor the company of "
        "your own user.")))
    out.append(_p(_(
        "Change the brand of a meeting that already has an Odoo videocall and "
        "its link follows immediately, keeping its access token: the "
        "invitations already sent keep working and only the domain in front of "
        "them changes.")))
    out.append(_note(_(
        "A meeting created before this field has no brand of its own and keeps "
        "following the company of its %(organiser)s, so updating the module "
        "does not move a single link. The field is only shown where choosing "
        "means something: one domain per company, and more than one company.",
        organiser=b % _("Organiser"))))

    out.append(_h(_("The name on the videocall page")))
    out.append(_p(_(
        "When the videocall link is pasted into WhatsApp, Telegram or Slack, "
        "the preview those apps build reads the title of the page it opens, "
        "and Odoo leaves that title as a bare %(odoo)s. The module writes the "
        "name of the brand the meeting goes out under instead.",
        odoo=b % "Odoo")))
    out.append(_p(_(
        "To announce a different name -- the brand your customers know rather "
        "than the legal name of the company -- fill in %(field)s, right under "
        "the domain, either in the settings or on the company itself.",
        field=b % _("Videocall page title"))))

    out.append(_h(_("Meetings that already exist")))
    out.append(_p(_(
        "A meeting stores its link when it is created, so changing the setting "
        "only reaches new ones. The %(button)s button rebuilds the videocall "
        "link of the meetings that have not happened yet.",
        button=b % _("Save and update upcoming meetings"))))
    out.append(_p(_(
        "It does not change their access token, so the invitations you already "
        "sent keep working: only the domain in front of them changes.")))

    out.append(_h(_("How it looks on the meeting")))
    out.append(_p(_(
        "Press the videocall button on the meeting as always. The link is "
        "built with the domain you configured.")))
    out.append(_img(folder, '04_reunion', _("A meeting with its videocall link")))

    out.append(_h(_("Online Appointments")))
    out.append(_p(_(
        "If you use Odoo's Online Appointments, a booking keeps the domain of "
        "the website it was booked on -- the one the attendee recognises, and "
        "the one Odoo already resolves for that kind of meeting. Only the "
        "meetings your team creates follow the domain configured here.")))

    out.append(_h(_("Questions")))
    out.append(
        '<ul>'
        + '<li>%s</li>' % _p(_(
            "%(q)s No. The system base URL is left untouched, which is the "
            "whole point: the portal, the website and your other modules keep "
            "reading the same value as before.",
            q=b % _("Does it change my base URL?")))
        + '<li>%s</li>' % _p(_(
            "%(q)s Yes. Set the option back to Odoo default and press the "
            "button to rebuild the upcoming links, or simply uninstall it.",
            q=b % _("Can I undo it?")))
        + '<li>%s</li>' % _p(_(
            "%(q)s The address is empty or malformed, or the meeting comes "
            "from an online appointment, which keeps its own website.",
            q=b % _("A meeting still shows the old domain.")))
        + '</ul>')

    return '\n'.join(out)


def _lang_for_manual(env):
    """Language to write the article in -- the one the company works in.

    The article body is not a translatable field, so this is a one-time
    choice. ``env.user`` is right when someone clicks Install in Apps, but in
    a migration it is ``__system__``, which is always en_US -- hence the chain.
    """
    active = set(env['res.lang'].search([]).mapped('code'))
    candidates = []
    if env.uid != SUPERUSER_ID:
        candidates.append(env.user.lang)
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    if admin:
        candidates.append(admin.sudo().lang)
    candidates.append(env.company.partner_id.lang)
    # A company with only Spanish active should not get an English manual just
    # because nobody ever set a user language.
    candidates.extend(sorted(c for c in active if not c.startswith('en')))
    candidates.append('en_US')
    for code in candidates:
        if code and code in active:
            return code
    return 'en_US'


def install_manual(env):
    """Create the manual, or refresh it if nobody has edited it.

    Silently does nothing where Knowledge is not installed, which is every
    Community database.

    Called from ``_register_hook`` rather than from ``post_init_hook`` or a
    migration script: both of those run while the module itself is loading,
    and ``knowledge`` loads *after* this module (it is deeper in the graph),
    so ``knowledge.article`` is not in the registry yet and the manual would
    be skipped without a word. ``_register_hook`` runs once the whole registry
    is up, which is the only moment both are guaranteed to exist.
    """
    if 'knowledge.article' not in env:
        return False

    lang = _lang_for_manual(env)
    module = env['ir.module.module'].sudo().search(
        [('name', '=', 'xb_calendar_domain')], limit=1)
    # The count of code translations is part of the stamp on purpose: during a
    # module upgrade the hook can run before this module's .po is available, and
    # the manual would be written in English and never revisited. Counting them
    # makes the next registry load see a different stamp and rebuild itself.
    loaded = len(code_translations.get_python_translations('xb_calendar_domain', lang))
    stamp = '%s|%s|%s' % (module.latest_version or '', lang, loaded)
    context = {'lang': lang}  # noqa: F841 -- read by _() through the frame
    body = build_body(env(context=dict(env.context, lang=lang)))
    title = _('Meeting links domain')
    params = env['ir.config_parameter'].sudo()
    article = env.ref(ARTICLE_XMLID, raise_if_not_found=False)

    if article and params.get_param(STAMP_PARAM) == stamp:
        # Cheap exit for the common case: this runs on every registry load,
        # and rebuilding 6 KB of HTML at every boot to find nothing changed
        # would be a silly tax.
        return article

    if article:
        # Refresh only what the customer has not touched: an edited manual is
        # theirs, and stomping it on every upgrade would be worse than stale.
        previous = params.get_param(CHECKSUM_PARAM) or ''
        current = _saved_checksum(article)
        if previous and previous != current and not _legacy_checksum_of_ours(
                previous, article):
            _logger.info('xb_calendar_domain: manual edited locally, left as is.')
            params.set_param(STAMP_PARAM, stamp)
            return article
        # The title is refreshed together with the body: we only get here when
        # the customer has not edited the article, and a manual whose body is in
        # Spanish but whose title stayed in English is worse than either.
        #
        # ``install_module`` is what keeps this write from crashing. Writing
        # ``body`` on a knowledge article runs the collaborative editor's
        # ``handle_history_divergence``, which announces the change on the bus
        # through ``request.env``. We run from ``_register_hook``, in the middle
        # of building the registry: when the load was triggered by an HTTP
        # request the proxy is bound but its ``env`` does not exist yet, so that
        # line raises ``'NoneType' object is not subscriptable`` and the manual
        # is left stale for good -- silently, since the hook catches it. Whether
        # a load happens to be request-bound is luck, which is exactly why this
        # only failed *sometimes*. The flag is the core's own way out
        # (``html_editor/tools.py``, the single place it is read): a write that
        # does not come from the editor has no history to diverge from.
        article.with_context(install_module=True).write(
            {'name': title, 'body': body})
    else:
        article = env['knowledge.article'].with_context(install_module=True).create({
            'name': title,
            'body': body,
            'icon': '🔗',
            'internal_permission': 'write',
            'is_article_visible_by_everyone': True,
        })
        env['ir.model.data'].create({
            'module': ARTICLE_XMLID.split('.')[0],
            'name': ARTICLE_XMLID.split('.')[1],
            'model': 'knowledge.article',
            'res_id': article.id,
            # noupdate is not about protecting edits here (the checksum above
            # does that, and finer): it is what keeps the record ALIVE.
            # ir.model.data._process_end deletes every xmlid of the module that
            # no data file claimed during the load -- and an article created by
            # a hook is exactly that -- taking the article with it. It skips
            # noupdate rows. Without this the manual is created and then
            # silently dropped at the end of the very same upgrade.
            'noupdate': True,
        })

    # The collaborative editor keeps a snapshot of its own; leaving history
    # behind an ORM write is what makes an article revert in the browser.
    if 'html_field_history' in article._fields:
        article.write({'html_field_history': False})
    params.set_param(CHECKSUM_PARAM, _saved_checksum(article))
    params.set_param(STAMP_PARAM, stamp)
    _logger.info('xb_calendar_domain: manual ready (article %s, %s).', article.id, lang)
    return article
