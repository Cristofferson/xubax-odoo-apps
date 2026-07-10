-- ---------------------------------------------------------------------------
-- Rename the XUBAX "Special Dates" modules to the xb_ vendor prefix.
--
--     special_dates          ->  xb_special_dates
--     special_dates_whatsapp ->  xb_special_dates_whatsapp
--
-- Run this ONCE, only on databases that ALREADY have the old modules
-- installed. Fresh installs from the Odoo Apps Store need nothing.
-- It preserves all data (reminders, schedules, activities, config).
--
-- Odoo has no native "rename module" feature, so the technical name is
-- switched at the database level and the code is reloaded under the new name.
--
-- Procedure:
--   1) Stop the Odoo service.
--   2) Replace the old addon folders with the renamed ones
--      (xb_special_dates, xb_special_dates_whatsapp) in your addons_path;
--      remove the old special_dates / special_dates_whatsapp folders.
--   3) psql -d YOUR_DB -f rename_from_special_dates.sql
--   4) Start Odoo updating the renamed modules:
--         odoo-bin -c <conf> -d YOUR_DB -u xb_special_dates,xb_special_dates_whatsapp --stop-after-init
--   5) Start the service normally.
--
-- Safe to run inside a transaction; nothing is committed on error.
-- ---------------------------------------------------------------------------
BEGIN;

-- ===================== special_dates -> xb_special_dates =====================

-- The module record itself.
UPDATE ir_module_module
   SET name = 'xb_special_dates'
 WHERE name = 'special_dates';

-- External IDs owned by the module: switch the module column, and also rewrite
-- any id whose NAME embeds the old technical name (e.g. group_special_dates_user),
-- matching what the renamed source now declares.
UPDATE ir_model_data
   SET module = 'xb_special_dates',
       name   = replace(name, 'special_dates', 'xb_special_dates')
 WHERE module = 'special_dates';

-- The auto-generated external id of the module record lives under 'base'.
UPDATE ir_model_data
   SET name = 'module_xb_special_dates'
 WHERE module = 'base' AND name = 'module_special_dates';

-- Any module that depends on the old technical name (e.g. the WhatsApp add-on).
UPDATE ir_module_module_dependency
   SET name = 'xb_special_dates'
 WHERE name = 'special_dates';

-- System parameter key namespaced by the module.
UPDATE ir_config_parameter
   SET key = 'xb_special_dates.pos_popup_interval_hours'
 WHERE key = 'special_dates.pos_popup_interval_hours';

-- ============ special_dates_whatsapp -> xb_special_dates_whatsapp ============

UPDATE ir_module_module
   SET name = 'xb_special_dates_whatsapp'
 WHERE name = 'special_dates_whatsapp';

UPDATE ir_model_data
   SET module = 'xb_special_dates_whatsapp',
       name   = replace(name, 'special_dates_whatsapp', 'xb_special_dates_whatsapp')
 WHERE module = 'special_dates_whatsapp';

UPDATE ir_model_data
   SET name = 'module_xb_special_dates_whatsapp'
 WHERE module = 'base' AND name = 'module_special_dates_whatsapp';

UPDATE ir_module_module_dependency
   SET name = 'xb_special_dates_whatsapp'
 WHERE name = 'special_dates_whatsapp';

COMMIT;
