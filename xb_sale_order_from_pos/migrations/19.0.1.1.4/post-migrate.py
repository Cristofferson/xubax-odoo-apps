# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS
import logging

_logger = logging.getLogger(__name__)

OLD_EMAIL_FROM = "{{ (object.user_id.email_formatted or object.company_id.email_formatted or user.email_formatted) }}"
NEW_EMAIL_FROM = "{{ (object.company_id.email_formatted or object.user_id.email_formatted or user.email_formatted) }}"


def migrate(cr, version):
    # The POS quotation email now leaves from the shop instead of the salesperson:
    # the customer knows the store, not who was at the till. The template is
    # noupdate, so an upgrade never rewrites it: switch the sender here, only where
    # it still has the old default (a sender someone typed by hand is kept).
    cr.execute(
        """
        UPDATE mail_template t
           SET email_from = %s
          FROM ir_model_data d
         WHERE d.module = 'xb_sale_order_from_pos'
           AND d.name = 'mail_template_pos_quotation_ticket'
           AND d.model = 'mail.template'
           AND t.id = d.res_id
           AND t.email_from = %s
        """,
        (NEW_EMAIL_FROM, OLD_EMAIL_FROM),
    )
    _logger.info("[XB-MIG 19.0.1.1.4] POS quotation email sender switched to the company (%s template)", cr.rowcount)
