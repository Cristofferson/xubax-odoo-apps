# -*- coding: utf-8 -*-
"""Cashier manual, shipped with the module as a Knowledge article.

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
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

ARTICLE_XMLID = 'xb_pos_taecel.article_cashier_manual'
CHECKSUM_PARAM = 'xb_pos_taecel.manual_checksum'
IMG_BASE = '/xb_pos_taecel/static/src/img/manual'


def _img(folder, name, alt):
    return (
        '<p><img src="%s/%s/%s.png" alt="%s" class="img-fluid" '
        'style="width:100%%;max-width:900px;border-radius:8px;"></p>'
        % (IMG_BASE, folder, name, alt)
    )


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


def build_body(env):
    """Return the manual as HTML, in the language of ``env``."""
    lang = env.context.get('lang') or 'en_US'
    # _() reads the language off the CALLING FRAME (tools.translate._get_lang):
    # a local named `context` carrying a lang is the first thing it looks for,
    # then a local `self` with an env. A plain `env` argument is not one of
    # them -- without this local the manual always came out in English, no
    # matter what env it was handed.
    context = {'lang': lang}  # noqa: F841 -- read by _() through the frame
    folder = 'es' if lang.startswith('es') else 'en'
    b = '<b>%s</b>'
    out = []
    add = out.append

    add(_p(_(
        "Sell airtime, data packages and bill payments without leaving the "
        "point of sale. Six steps, under thirty seconds a sale. Everything is "
        "charged on the same ticket as the rest of the basket: there is no "
        "separate till and no separate closing.")))

    add('<h2>%s</h2>' % _("Before you start"))
    add(_p(_(
        "The %(button)s button shows up inside the point of sale once the shop "
        "has its recharges account connected. If you cannot see it, it is not "
        "hidden: that register has no account yet, and the manager sets that up.",
        button=b % _("Recharges"))))

    add('<h2>%s</h2>' % _("1 - Open the Recharges button"))
    add(_p(_(
        "With the order open, tap the three-dot button under the order, next "
        "to %(customer)s and %(note)s. %(recharges)s is in there.",
        customer=b % _("Customer"), note=b % _("Note"),
        recharges=b % _("Recharges"))))
    add(_img(folder, '01_boton', _("Point of sale actions panel with the Recharges button")))

    add('<h2>%s</h2>' % _("2 - Pick the carrier or the service"))
    add(_p(_(
        "The full list opens: mobile carriers at the top, services (power, "
        "cable, internet, pay TV) further down. It is the catalog your provider "
        "publishes, so if it shows here, it can be sold.")))
    add(_img(folder, '02_companias', _("List of carriers and services")))

    add('<h2>%s</h2>' % _("3 - Tap the amount the customer asked for"))
    add(_p(_(
        "Each carrier brings its own amounts and packages, with the validity "
        "that applies to them. For an open-amount service -- a power bill, say "
        "-- you get a field to type the exact amount instead of the list.")))
    add(_img(folder, '03_montos', _("Amounts and packages for the carrier")))

    add('<h2>%s</h2>' % _("4 - Type the number, twice"))
    add(_p(_(
        "Type the phone number or the bill reference, then type it again "
        "below. If the two do not match, you cannot continue. The length is "
        "checked against what that carrier expects.")))
    add(_p(_(
        "Underneath you get the breakdown: the amount, the fee charged to the "
        "customer and the total. No mental arithmetic.")))
    add(_img(folder, '04_referencia', _("Reference capture with confirmation and breakdown")))
    add(_note(_(
        "%(before)s read the number out loud to the customer and have them "
        "confirm it. %(warning)s -- not by you and not by the provider. It is "
        "the one step in the process with no way back.",
        before=b % _("Before you add it:"),
        warning=b % _("A recharge that has been sent cannot be cancelled or refunded"))))

    add('<h2>%s</h2>' % _("5 - Add it to the sale"))
    add(_p(_(
        "The recharge goes in as one more line of the order. The carrier and "
        "the number are written under the line, so you can check them at a "
        "glance before charging. Got it wrong? You can still delete the line: "
        "nothing has been sent until you take the money.")))
    add(_img(folder, '05_linea', _("The recharge as an order line")))

    add('<h2>%s</h2>' % _("6 - Charge as usual"))
    add(_p(_(
        "Cash, card or whatever method you normally use, and validate. "
        "Validating is when the recharge goes out to the carrier. You can sell "
        "a recharge together with the groceries on the same ticket.")))
    add(_img(folder, '09_cobro', _("Payment screen")))

    add('<h2>%s</h2>' % _("Bill payments: power, water, cable..."))
    add(_p(_(
        "Taking a bill is the same flow with one change. In the list, next to "
        "the mobile carriers, are the services: power, water, gas, cable, "
        "internet, pay TV and several government offices. Pick the one on the "
        "customer's bill.")))
    add(_img(folder, '06_servicios', _("List of services")))
    add(_p(_(
        "The difference: a service has %(no_fixed)s. Instead you type two "
        "things off the bill -- the %(amount)s the customer is paying and the "
        "%(number)s (or contract number). As with a phone, the reference is "
        "typed twice to confirm it.",
        no_fixed=b % _("no fixed amounts"), amount=b % _("amount"),
        number=b % _("service number"))))
    add(_img(folder, '07_servicio_captura', _("Capturing a bill payment: amount and service number")))
    add(_p(_(
        "From there everything is identical: %(add)s puts the payment in as "
        "one more line, and you charge it all together on the same ticket. One "
        "sale can carry the groceries, a phone top-up and the power bill.",
        add=b % _("Add to sale"))))
    add(_img(folder, '08_dos_lineas', _("A top-up and a bill payment on the same order")))
    add(_note(_(
        "%(watch)s the amount on a service is typed by you off the bill. Check "
        "it with the customer before adding the line: just like a recharge, "
        "%(sent)s.",
        watch=b % _("Watch the amount:"),
        sent=b % _("a payment that has been sent cannot be cancelled"))))

    add('<h2>%s</h2>' % _("If a recharge comes back rejected"))
    add(_p(_(
        "A recharge is not sent while the customer waits: the carrier is "
        "allowed up to a minute to answer, and nobody is going to hold the "
        "queue for that. It goes out the moment you validate, and the answer "
        "comes back seconds later -- by then the ticket has printed and you "
        "may already be on another sale.")))
    add(_p(_(
        "So the till tells you. If it came back rejected, a message pops up on "
        "the screen wherever you are, with the reason and %(how_much)s:",
        how_much=b % _("how much to refund"))))
    add(_img(folder, '10_aviso', _("Rejected recharge notice at the till")))
    add(_table(
        [_("What it says"), _("What it means"), _("What you do")],
        [
            [b % _("Recharge failed"),
             _("The carrier rejected it. The money was not spent."),
             _("Refund that line to the customer. Nothing was delivered.")],
            [b % _("Recharge unconfirmed"),
             _("The carrier has not answered yet. It may still go through."),
             _("%(dont)s. It is being verified and settles on its own.",
               dont=b % _("Do NOT refund it and do NOT sell it again"))],
        ]))
    add(_note(_(
        "%(why)s refunding a recharge that did arrive is giving money away, "
        "and selling it again puts credit on the customer's phone twice, with "
        "the shop paying for both. That is why the two notices read "
        "differently: one asks you to refund, the other asks you to wait.",
        why=b % _("Why the difference:"))))
    add(_p(_(
        "Tapping %(ok)s marks the notice as seen on the server, not just in "
        "this browser: reloading the screen will not lose it, and it will not "
        "pop up again on the next shift.", ok=b % _("Understood"))))

    add('<h2>%s</h2>' % _("For the manager"))
    add(_p(_(
        "Every sale leaves its own transaction under %(menu)s, with the folio "
        "the carrier returns, the amount, the fee charged to the customer and "
        "the point-of-sale order it came from.",
        menu=b % _("Recharges > Transactions"))))
    add(_img(folder, '11_transacciones', _("Transactions list")))
    add(_table(
        [_("State"), _("Means")],
        [
            [b % _("Draft"), _("The sale was charged and the recharge is queued to go out.")],
            [b % _("Sent"), _("It has been requested and the confirmation is pending.")],
            [b % _("Successful"), _("The carrier credited it and returned a folio. This is the only state that spends balance for good.")],
            [b % _("Failed"), _("The carrier rejected it. The amount is refunded to your wallet automatically.")],
        ]))
    add('<ul>'
        + '<li>%s</li>' % _p(_(
            "%(balance)s Each wallet (airtime, bill payments) refreshes on its "
            "own every half hour, and on demand with the %(refresh)s button on "
            "the account. If a wallet runs short, the till warns before it lets "
            "a sale through.", balance=b % _("Balance."), refresh=b % _("Refresh Balance")))
        + '<li>%s</li>' % _p(_(
            "%(reco)s Recharges left unconfirmed are checked automatically "
            "every few minutes until they close. Nothing to do by hand.",
            reco=b % _("Reconciliation.")))
        + '<li>%s</li>' % _p(_(
            "%(fee)s What the customer is charged on top comes from each "
            "carrier's configuration, not from the till. It is usually zero on "
            "airtime; on bill payments is where it shows up.", fee=b % _("Customer fee.")))
        + '</ul>')

    add('<h2>%s</h2>' % _("Funding the wallets"))
    add(_p(_(
        "Airtime and bill payments are funded separately and balance is never "
        "moved between them, so each one has %(own)s. Depositing with the "
        "wrong one leaves the money stuck in the wrong wallet.",
        own=b % _("its own deposit reference"))))
    add(_img(folder, '12_cuenta', _("Account form with the deposit references")))
    add(_p(_(
        "The %(sheet)s button prints a page with both references and the bank "
        "details, ready to hand to whoever makes the deposit. The reference is "
        "yours for good: the deposit is credited to your account "
        "automatically, with no transfer to wait on.", sheet=b % _("Deposit Sheet"))))

    add('<h2>%s</h2>' % _("Questions that come up"))
    add('<ul>'
        + '<li>%s</li>' % _p(_(
            "%(q)s No. Successful recharges are not cancelled by anyone. That "
            "is why the number is typed twice and confirmed with the customer "
            "before the line is added.",
            q=b % _("Can I cancel a recharge I already charged?")))
        + '<li>%s</li>' % _p(_(
            "%(q)s If the recharge made it out, it is on record and closes "
            "itself when the connection is back. If it did not, nothing was "
            "sent. It is never sent twice.",
            q=b % _("What if the power or the internet drops mid-sale?")))
        + '<li>%s</li>' % _p(_(
            "%(q)s Yes. Once a folio comes back it is printed on the ticket "
            "along with the carrier and the number, which is what the customer "
            "needs in order to claim.", q=b % _("Does the ticket carry the folio?")))
        + '<li>%s</li>' % _p(_(
            "%(q)s Yes, it is one more line of the order. It is charged "
            "together and lands in the same till closing.",
            q=b % _("Can I sell a recharge and the groceries on one ticket?")))
        + '<li>%s</li>' % _p(_(
            "%(q)s That register has no account connected, or the account is "
            "restricted to other registers. The manager checks it under "
            "%(menu)s.", q=b % _("The Recharges button is not there."),
            menu=b % _("Recharges > Account")))
        + '</ul>')

    return '\n'.join(out)


def _lang_for_manual(env):
    """Language to write the article in -- the one the shop works in.

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
    # A shop with only Spanish active should not get an English manual just
    # because nobody ever set a user language.
    candidates.extend(sorted(c for c in active if not c.startswith('en')))
    candidates.append('en_US')
    for code in candidates:
        if code and code in active:
            return code
    return 'en_US'


def install_manual(env):
    """Create the cashier manual, or refresh it if nobody has edited it.

    Silently does nothing where Knowledge is not installed, which is every
    Community database.
    """
    if 'knowledge.article' not in env:
        return False

    lang = _lang_for_manual(env)
    context = {'lang': lang}  # noqa: F841 -- read by _() through the frame
    body = build_body(env(context=dict(env.context, lang=lang)))
    digest = hashlib.sha256(body.encode()).hexdigest()
    params = env['ir.config_parameter'].sudo()
    article = env.ref(ARTICLE_XMLID, raise_if_not_found=False)

    if article:
        # Refresh only what the customer has not touched: an edited manual is
        # theirs, and stomping it on every upgrade would be worse than stale.
        previous = params.get_param(CHECKSUM_PARAM)
        current = hashlib.sha256((article.body or '').encode()).hexdigest()
        if previous and previous != current:
            _logger.info('xb_pos_taecel: cashier manual edited locally, left as is.')
            return article
        if previous == digest:
            return article
        article.write({'body': body})
    else:
        title = _('Recharges and bill payments at the till')
        article = env['knowledge.article'].create({
            'name': title,
            'body': body,
            'icon': '📶',
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
    params.set_param(CHECKSUM_PARAM, digest)
    _logger.info('xb_pos_taecel: cashier manual ready (article %s, %s).', article.id, lang)
    return article
