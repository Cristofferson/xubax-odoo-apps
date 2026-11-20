# -*- coding: utf-8 -*-
"""Price checker manual, shipped with the module as a Knowledge article.

Why it lives in Python instead of a data XML: the article is only created
where Knowledge is installed (it is an Enterprise app), and making the module
depend on it would lock every Community buyer out. A hook can ask.

Why the body is built from _() calls instead of a static HTML file: the
article body is a plain html field, not a translatable one, so the language
has to be chosen when the record is written. Building it from translated
strings gives one source and any language the .po covers.
"""
import hashlib
import logging

from odoo import SUPERUSER_ID
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

ARTICLE_XMLID = 'xb_price_checker.article_manual'
CHECKSUM_PARAM = 'xb_price_checker.manual_checksum'        # body as stored
SOURCE_PARAM = 'xb_price_checker.manual_source_checksum'    # body as generated
IMG_BASE = '/xb_price_checker/static/src/img/manual'


def _img(name, alt, width=900):
    return (
        '<p><img src="%s/%s.jpg" alt="%s" class="img-fluid" '
        'style="width:100%%;max-width:%spx;border-radius:8px;"></p>'
        % (IMG_BASE, name, alt, width)
    )


def _p(text):
    return '<p><span style="font-size: 14px;">%s</span></p>' % text


def _caption(text):
    return '<p><em>%s</em></p>' % text


def _note(text):
    return '<blockquote>%s</blockquote>' % _p(text)


def _list(items, ordered=False):
    tag = 'ol' if ordered else 'ul'
    return '<%s>%s</%s>' % (tag, ''.join('<li>%s</li>' % _p(i) for i in items), tag)


def _table(head, rows):
    return (
        '<table class="table table-bordered"><tbody><tr>%s</tr>%s</tbody></table>'
        % (''.join('<td><strong>%s</strong></td>' % h for h in head),
           ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % c for c in row) for row in rows))
    )


def build_body(env):
    """Return the manual as HTML, in the language of ``env``."""
    lang = env.context.get('lang') or 'en_US'
    # _() reads the language off the CALLING FRAME: a local named `context`
    # carrying a lang is the first thing it looks for (see xb_pos_taecel).
    context = {'lang': lang}  # noqa: F841 -- read by _() through the frame
    b = '<b>%s</b>'
    out = []
    add = out.append

    # What it is
    add('<h2>%s</h2>' % _("What it is"))
    add(_p(_(
        "The Price checker is a screen for your customers: they scan a product and "
        "see what it costs, without asking anyone. It is an Odoo app and it works "
        "even if you do not have XPago.")))
    add(_p(_("When a product is scanned, the screen shows:")))
    add(_list([
        _("%(what)s of the product, with its reference.", what=b % _("Photo and name")),
        _("%(what)s, with the pricelist and taxes of the register you chose.", what=b % _("Price")),
        _("%(what)s, only when the product has a discount.",
          what=b % _("Price before and discount percentage")),
        _("%(what)s: \"Available in this store\" or \"Out of stock in this store\". "
          "It never says how many pieces there are.", what=b % _("Stock")),
        _("%(what)s, for example \"Up to 12 months without interest of $1,250.00\". "
          "It only appears if you have the XPago app with payment rules.",
          what=b % _("Months without interest")),
    ]))
    add(_p(_(
        "After a few seconds the screen goes back to \"Check the price\" by itself, "
        "ready for the next customer.")))
    add(_p(_("It can be used in two ways:")))
    add(_list([
        _("%(what)s with a barcode scanner, by opening a link.",
          what=b % _("On any tablet, phone or screen")),
        _("%(what)s, as one more app.", what=b % _("On the XPago terminal")),
    ], ordered=True))

    # How it looks
    add('<h2>%s</h2>' % _("How it looks"))
    add(_p(_(
        "The customer holds the barcode to the scanner. The device asks your Odoo "
        "and the product shows up within a second. There is no need to touch the screen.")))
    add(_p(_(
        "If the product has no barcode, the customer can tap \"Type the code\" and "
        "write the internal reference. This option is only in the link version "
        "(tablet or screen).")))
    add(_img('terminal', _("Customer scanning a bag with the XPago terminal in a boutique"), 480))
    add(_caption(_(
        "With the XPago terminal: the customer scans the tag and sees photo, price, "
        "discount, months and stock.")))
    add(_img('screen', _("Customer scanning a ring box in front of a wall screen in a jewelry store")))
    add(_caption(_("With a wall screen and a fixed scanner, using the link.")))

    # What you need
    add('<h2>%s</h2>' % _("What you need"))
    add(_table(
        [_("What"), _("With the link (tablet or screen)"), _("With the XPago terminal")],
        [
            [_("Odoo"), _("17, 18, 19 or 20, Community or Enterprise"), _("The same")],
            [_("Odoo apps"), _("Point of Sale and Price checker"),
             _("Point of Sale, Price checker and XPago")],
            [_("Device"), _("Tablet, phone or computer with a browser"),
             _("XPago terminal with app 0.9.0 or newer")],
            [_("Scanner"), _("One that types the code and presses Enter (USB, Bluetooth or built in)"),
             _("The terminal's scanner")],
            [_("Internet"), _("Yes"), _("Yes")],
            [_("Odoo user on the device"), _("No"), _("Yes: the terminal must be logged in")],
        ]))
    add(_p(_(
        "To show %(stock)s you need the Inventory app and the product must track "
        "inventory. Otherwise that line does not appear.", stock=b % _("stock"))))

    # Install and set up
    add('<h2>%s</h2>' % _("Install and set up"))
    add(_list([
        _("In Odoo go to %(apps)s, search for \"Price checker\" and install it.", apps=b % _("Apps")),
        _("Go to %(menu)s.", menu=b % _("Point of Sale > Configuration > Settings")),
        _("At the top, choose the %(register)s whose prices you want to show. The checker "
          "uses the pricelist, the taxes and the warehouse of that register.", register=b % _("register")),
        _("Scroll down to the %(block)s block and adjust what you need: "
          "%(stock)s says whether that store has it (on by default); "
          "%(months)s is on by default and only shows if you have the XPago app; "
          "%(back)s is the seconds a product stays on screen (15 by default).",
          block=b % _("Price checker"), stock=b % _("Show stock"),
          months=b % _("Show months without interest"), back=b % _("Back to the start")),
        _("Save."),
    ], ordered=True))
    add(_p(_(
        "Each register has its own price checker. If you have two stores with "
        "different prices, set up each register separately.")))

    # On a tablet or screen
    add('<h2>%s</h2>' % _("Using it on a tablet or screen"))
    add(_list([
        _("In %(menu)s, with the register chosen, tap %(open)s. The first time, the "
          "register's link is created and shows under the button, with a button to copy it.",
          menu=b % _("Point of Sale > Configuration > Settings"), open=b % _("Open the price checker")),
        _("Open that link on the store's tablet or screen. No user or password is needed."),
        _("Plug in the scanner. The screen shows \"Check the price\" and it is ready."),
        _("Leave it open. If the browser has a full screen or kiosk mode, use it so "
          "the customer cannot leave the page."),
    ], ordered=True))
    add(_note(_(
        "%(key)s Anyone who has it sees the prices of that register. If it is shared "
        "by mistake, tap %(new)s: the screens with the previous link stop working and "
        "the new one has to be opened on each of them.",
        key=b % _("The link is the key."), new=b % _("New link"))))

    # On the XPago terminal
    add('<h2>%s</h2>' % _("Using it on the XPago terminal"))
    add(_p(_(
        "The terminal does not use the link: it uses the Odoo session it is already logged in with.")))
    add(_p(b % _("Turning it on (only once):")))
    add(_list([
        _("Open the Odoo app of the terminal, logged in."),
        _("Tap the %(menu)s button and choose %(item)s.",
          menu=b % "☰", item=b % _("Verificador de precios (para clientes)")),
        _("Choose the register: \"¿Los precios de qué caja muestra?\"."),
        _("The \"Listo\" notice appears and a new icon is left among the terminal's apps: "
          "%(icon)s.", icon=b % _("Verificador de precios")),
    ], ordered=True))
    add(_p(b % _("Using it:")))
    add(_list([
        _("Tap the %(icon)s icon. The terminal stays on \"Check the price\", full screen "
          "and locked: the customer cannot leave it or open other apps.",
          icon=b % _("Verificador de precios")),
        _("The customer scans with the terminal's scanner."),
        _("Each product stays on screen for 15 seconds and then goes back to the start. "
          "On the terminal this time is fixed; the \"Back to the start\" setting only "
          "changes the link version."),
    ]))
    add(_p(b % _("Leaving it:")))
    add(_list([
        _("Press and hold the top left corner for 5 seconds."),
        _("Type the %(pin)s and tap %(exit)s. The PIN of an employee whose user is a Point of "
          "Sale administrator works, or that of a manager of that register.",
          pin=b % _("PIN of a manager"), exit=b % _("Salir")),
        _("After 5 wrong PINs you have to wait one minute."),
    ], ordered=True))
    add(_p(_(
        "When you leave, the chosen register stays saved: the icon opens the price checker again.")))
    add(_p(_(
        "%(remove)s in the Odoo app of the terminal, tap %(item)s. The icon disappears.",
        remove=b % _("Removing it:"), item=b % _("☰ > Quitar el verificador de precios"))))

    # Where each figure comes from
    add('<h2>%s</h2>' % _("Where each figure comes from"))
    add(_p(_(
        "Everything comes from Odoo at the moment of the scan. If you change a price "
        "in Odoo, the checker shows it on the next scan.")))
    add(_table(
        [_("Figure"), _("Where it comes from")],
        [
            [_("Product"), _("It looks first by barcode and then by internal reference "
                             "(upper or lower case alike). Only products marked \"Can be Sold\" "
                             "and of your company.")],
            [_("Price"), _("The pricelist of the register, for one piece. With or without "
                           "taxes, the same way the register shows prices.")],
            [_("Price before and discount"), _("The sales price of the product. It only shows "
                                               "if the pricelist gives at least 0.5% less.")],
            [_("Stock"), _("The pieces available and not reserved in the register's warehouse. "
                           "It only says whether there are any or not.")],
            [_("Months without interest"), _("The most months the XPago payment rules allow "
                                             "for that product and that price. If the rules "
                                             "give a single payment, it does not appear.")],
            [_("Language"), _("The language of your company in Odoo.")],
        ]))

    # Common problems
    add('<h2>%s</h2>' % _("Common problems"))
    add(_table(
        [_("What happens"), _("What to do")],
        [
            [_("\"We could not find this product\""),
             _("Check that the product has that barcode or that internal reference in Odoo "
               "and that it is marked \"Can be Sold\".")],
            [_("\"No connection, try again\""),
             _("The device lost internet or Odoo did not answer. Check the internet and scan again.")],
            [_("The link says the page does not exist"),
             _("Someone tapped New link. Open the new link from Settings.")],
            [_("The scanner does nothing on the tablet"),
             _("Tap the screen once. Check that the scanner types into a notepad and presses Enter at the end.")],
            [_("The stock line does not show"),
             _("Turn on Show stock and check that the product tracks inventory.")],
            [_("The months without interest do not show"),
             _("Turn on Show months without interest, check that you have the XPago app and "
               "that a payment rule gives months to that product and price.")],
            [_("Terminal: \"Falta instalar «Verificador de precios» en tu Odoo\""),
             _("Install the app in your Odoo (Install and set up section).")],
            [_("Terminal: \"No pude traer las cajas de tu Odoo\""),
             _("The terminal is not logged in to Odoo. Log in with your user and try again.")],
            [_("Terminal: \"Tu Odoo no tiene cajas de Punto de venta\""),
             _("Create a register in Point of Sale. The checker uses its prices.")],
            [_("Terminal: \"NIP incorrecto\""),
             _("Use the PIN of a manager. After 5 failed tries, wait one minute.")],
        ]))
    add(_p(_("Support: %(mail)s", mail='<a href="mailto:soporte@xubax.com">soporte@xubax.com</a>')))

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
        # Refresh only what the customer has not touched (see xb_pos_taecel for
        # why there are two checksums).
        previous = params.get_param(CHECKSUM_PARAM)
        current = hashlib.sha256((article.body or '').encode()).hexdigest()
        by_us = article.write_uid.id == SUPERUSER_ID
        if previous and previous != current and not by_us:
            _logger.info('xb_price_checker: manual edited locally, left as is.')
            return article
        if params.get_param(SOURCE_PARAM) == digest:
            return article
        article.write({'body': body})
    else:
        title = _('Price checker: manual')
        article = env['knowledge.article'].create({
            'name': title,
            'body': body,
            'icon': '🏷️',
            'internal_permission': 'write',
            'is_article_visible_by_everyone': True,
        })
        env['ir.model.data'].create({
            'module': ARTICLE_XMLID.split('.')[0],
            'name': ARTICLE_XMLID.split('.')[1],
            'model': 'knowledge.article',
            'res_id': article.id,
            # noupdate keeps the record ALIVE: _process_end deletes every xmlid
            # of the module that no data file claimed, except noupdate ones.
            'noupdate': True,
        })

    if 'html_field_history' in article._fields:
        article.write({'html_field_history': False})
    params.set_param(CHECKSUM_PARAM, hashlib.sha256((article.body or '').encode()).hexdigest())
    params.set_param(SOURCE_PARAM, digest)
    _logger.info('xb_price_checker: manual ready (article %s, %s).', article.id, lang)
    return article
