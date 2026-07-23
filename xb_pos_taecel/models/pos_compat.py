# -*- coding: utf-8 -*-
"""Odoo 18 / 19 compatibility shim.

This module ships for both Odoo 18 and Odoo 19 from a single codebase. The POS
loading API changed between them, in two ways that reach our models:

    Odoo 18                                  Odoo 19
    ---------------------------------------  ------------------------------------
    _load_pos_data_domain(self, data)        _load_pos_data_domain(self, data, config)
    _load_pos_data_fields(self, config_id)   _load_pos_data_fields(self, config)
    `config_id` is an int (the id)           `config` is a pos.config recordset

Both are absorbed here so no other Python file needs a version check:

    * declare the hooks with ``config=None`` so either call arity binds;
    * run whatever you receive through :func:`pos_config_record` to always end
      up with a recordset.

Keep every version divergence in this file. Its JS counterpart is
``static/src/app/compat.js``, which is the only asset that differs between the
18.0 and 19.0 branches.
"""
from odoo import models, release
from odoo.models import BaseModel

#: Major Odoo version this instance runs (18, 19, ...).
#: On SaaS builds ``version_info[0]`` is a *string* ('saas~18'), not an int, so
#: keep only the digits before comparing -- ``'saas~18' <= 18`` raises TypeError.
_MAJOR = str(release.version_info[0]).split('.')[0]
ODOO_VERSION = int(''.join(c for c in _MAJOR if c.isdigit()) or 0)
IS_ODOO_18 = ODOO_VERSION <= 18

#: Odoo 19 replaced ``_sql_constraints`` with ``models.Constraint`` table
#: objects, and *ignores* the old attribute with nothing but a WARNING in the
#: log -- the constraints are silently never created. Odoo 18 has no
#: ``models.Constraint``. Models pick the right one with this flag.
HAS_MODEL_CONSTRAINT = hasattr(models, 'Constraint')


def pos_config_record(env, config):
    """Return a ``pos.config`` recordset from whatever the POS handed us.

    Accepts an id (Odoo 18), a recordset (Odoo 19), or nothing at all, and
    always returns a recordset -- empty rather than None, so callers can chain
    without guarding.
    """
    if isinstance(config, BaseModel):
        return config
    if isinstance(config, int):
        return env['pos.config'].browse(config)
    return env['pos.config']
