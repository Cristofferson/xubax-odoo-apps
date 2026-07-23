# -*- coding: utf-8 -*-
import logging

from . import manual_content

_logger = logging.getLogger(__name__)


def _xb_vbpk_pick_language(env):
    """Which language to write the manual in.

    A Knowledge article holds a single body — it is not a translatable field —
    so one manual is created in the language that best fits this database: the
    main company's language decides. A Spanish company gets the Spanish manual,
    anyone else gets the English one.
    """
    lang = (env.company.partner_id.lang
            or env.context.get("lang")
            or "en_US")
    return "es" if lang.startswith("es") else "en"


def _xb_vbpk_post_init(env):
    """Create the user manual in Knowledge, once.

    The articles are ordinary records afterwards — the user can edit, translate,
    duplicate or delete them freely, and this hook never runs again to overwrite
    them.
    """
    Article = env["knowledge.article"].sudo()

    # Idempotency: if a manual root already exists (in either language), do
    # nothing — including a hand-made one an early adopter may already have.
    if Article.search_count([
        ("parent_id", "=", False),
        ("name", "in", [manual_content.ROOT["name_en"],
                        manual_content.ROOT["name_es"]]),
    ]):
        _logger.info("Vendor bill products: manual already present, skipped.")
        return

    suffix = _xb_vbpk_pick_language(env)

    def _create(node, parent=False, seq=0):
        vals = {
            "name": node["name_%s" % suffix],
            "body": node["body_%s" % suffix],
            "icon": node["icon"],
            "parent_id": parent,
            "sequence": seq,
        }
        if not parent:
            vals["internal_permission"] = "write"
            vals["is_article_visible_by_everyone"] = True
        return Article.create(vals)

    root = _create(manual_content.ROOT)
    for index, section in enumerate(manual_content.SECTIONS, start=1):
        _create(section, parent=root.id, seq=index * 10)

    _logger.info("Vendor bill products: user manual created in '%s' "
                 "(root %s, %s sections).",
                 suffix, root.id, len(manual_content.SECTIONS))
