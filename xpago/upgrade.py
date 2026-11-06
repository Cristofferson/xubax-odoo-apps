"""XPago used to ship as three apps. Their records move to the new modules (xpago, and the xpago_pos and
xpago_self_order bridges that install by themselves) so that nothing is recreated or deleted:
settings, deposit accounts, payment rules, terminal charges and payments stay as they were."""
import logging

_logger = logging.getLogger(__name__)

FOLDED_MODULES = {
    'xpago': ('payment_xpago',),
    'xpago_pos': ('pos_xpago',),
    'xpago_self_order': ('pos_self_order_xpago',),
}

# Records whose name was used by more than one of the former apps.
RENAMED = {
    ('pos_xpago', 'payment_xpago_rule_view_list'): 'pos_payment_xpago_rule_view_list',
    ('pos_xpago', 'payment_xpago_rule_view_form'): 'pos_payment_xpago_rule_view_form',
}


def fold_old_modules(cr, target):
    """Run before ``target`` loads its data (pre_init_hook). Moves the records of the former apps to ``target`` and
    retires those apps, whose code is gone."""
    old_modules = FOLDED_MODULES[target]
    cr.execute("SELECT name FROM ir_module_module WHERE name IN %s AND state IN ('installed', 'to upgrade', 'to remove')",
               [old_modules])
    present = [row[0] for row in cr.fetchall()]
    if not present:
        return
    cr.execute("SELECT id FROM ir_module_module WHERE name = %s", [target])
    target_id = cr.fetchone()[0]
    for (module, name), new_name in RENAMED.items():
        if module in present:
            cr.execute("UPDATE ir_model_data SET name = %s WHERE module = %s AND name = %s", [new_name, module, name])
    for module in present:
        cr.execute("""
            UPDATE ir_model_data old SET module = %s
             WHERE old.module = %s
               AND NOT EXISTS (SELECT 1 FROM ir_model_data new WHERE new.module = %s AND new.name = old.name)
        """, [target, module, target])
        # A record both former apps declared (none today) stays with the first one moved.
        cr.execute("DELETE FROM ir_model_data WHERE module = %s", [module])
        for table in ('ir_model_constraint', 'ir_model_relation'):
            cr.execute(f"""
                UPDATE {table} SET module = %s
                 WHERE module = (SELECT id FROM ir_module_module WHERE name = %s)
            """, [target_id, module])
        # QWeb templates are found by their key, which starts with the module.
        cr.execute("UPDATE ir_ui_view SET key = %s || substr(key, length(%s) + 1) WHERE key LIKE %s",
                   [target + '.', module + '.', module + '.%'])
        # The former app is retired: its code is gone, and it must not be loaded or uninstalled again.
        cr.execute("UPDATE ir_module_module SET state = 'uninstalled', latest_version = NULL WHERE name = %s", [module])
        _logger.info("XPago: the records of %s now belong to %s", module, target)
    if target == 'xpago':
        # The provider's module decides its install state and what its uninstall resets.
        cr.execute("UPDATE payment_provider SET module_id = %s WHERE code = 'xpago'", [target_id])
