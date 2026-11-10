# -*- coding: utf-8 -*-
"""Keep registers of other companies selling, now that the rule is explicit.

Until this version an account was offered to every register regardless of
company, and the order hook fell back to "any active account". That is what let
one parent account serve a whole group -- and also what silently took money for
recharges it then refused to dispatch.

From now on a company either owns the account or is listed on it
(``shared_company_ids``). Existing installations must not lose the button
overnight, so whichever companies were in fact selling on an account are
written onto it here: same behaviour as yesterday, stated out loud.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return  # fresh install: nothing was relying on the implicit rule
    env = api.Environment(cr, SUPERUSER_ID, {})
    accounts = env['xb.taecel.account'].search([])
    if not accounts:
        return
    configs = env['pos.config'].search([])
    # A company that owns an account of its own was already served by it; only
    # the companies that had no account of their own were borrowing one.
    borrowing = configs.mapped('company_id') - accounts.mapped('company_id')
    for account in accounts:
        served = configs if not account.config_ids else account.config_ids
        companies = (served.mapped('company_id') & borrowing) - account.company_id
        if companies:
            account.shared_company_ids = [(4, company.id) for company in companies]
            _logger.info(
                'xb_pos_taecel: account %s now explicitly shared with %s',
                account.display_name, ', '.join(companies.mapped('name')))
