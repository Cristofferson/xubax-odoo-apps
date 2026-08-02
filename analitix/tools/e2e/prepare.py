# -*- coding: utf-8 -*-
"""Set up an Odoo database for the end-to-end run, and print what it made.

Run through ``odoo-bin shell``. It is deliberately separate from the E2E scripts
themselves: those talk to the product only through HTTP and the browser, the way
a customer's installation does, and something has to create the store and issue
the key first — the same way an implementer would.

Everything it creates is prefixed ``e2e`` so a run can be repeated on the same
database without colliding with the demo data or with a previous run.
"""
import json
import sys

from odoo import fields

Store = env["analitix.store"].sudo()
Door = env["analitix.door"].sudo()
Device = env["analitix.device"].sudo()
Users = env["res.users"].sudo()
param = env["ir.config_parameter"].sudo()

# The lab override. The ingest endpoint refuses plaintext, which is right in
# production and impossible on a loopback test rig — this is the documented
# switch for exactly that, and exercising it here also proves it works.
param.set_param("analitix.allow_insecure_ingest", "1")

store = Store.search([("code", "=", "E2E")], limit=1)
if not store:
    store = Store.create({
        "name": "E2E Store",
        "code": "E2E",
        "company_id": env.company.id,
        "tz": "UTC",
        "match_mode": "registers",
        "area_sqm": 120.0,
        # Short windows so the run does not have to wait a realistic amount of
        # time to observe a realistic behaviour.
        "reid_ttl_minutes": 60,
        "visit_gap_minutes": 30,
        "offline_threshold_min": 5,
        "degraded_threshold_min": 2,
        "lost_sale_enabled": True,
        "reid_enabled": True,
    })
    front = Door.create({
        "store_id": store.id, "name": "E2E Front", "code": "F"})
    Door.create({
        "store_id": store.id, "name": "E2E Staff", "code": "S",
        "kind": "service", "counts_visitors": False})
    Device.create({
        "name": "E2E front counter", "device_uid": "e2e-front",
        "store_id": store.id, "door_id": front.id, "role": "door_counter",
    })

device = Device.search([("device_uid", "=", "e2e-front")], limit=1)
# A fresh key every run: it is shown once and the previous run's is a hash.
key = device._issue_key()

# A second store, of a second "customer", so the isolation checks have
# something real to fail against.
other = Store.search([("code", "=", "E2EOTHER")], limit=1)
if not other:
    other = Store.create({
        "name": "E2E Other Customer", "code": "E2EOTHER",
        "company_id": env.company.id, "tz": "UTC",
    })
    other_door = Door.create({
        "store_id": other.id, "name": "Other Front", "code": "OF"})
    Device.create({
        "name": "Other counter", "device_uid": "e2e-other",
        "store_id": other.id, "door_id": other_door.id})
other_device = Device.search([("device_uid", "=", "e2e-other")], limit=1)
other_key = other_device._issue_key()

# A user scoped to the first store only. The browser run logs in as this person
# and must not be able to reach the second store by any route.
scoped = Users.with_context(active_test=False).search(
    [("login", "=", "e2e_scoped")], limit=1)
if not scoped:
    scoped = Users.with_context(no_reset_password=True).create({
        "name": "E2E Scoped Manager",
        "login": "e2e_scoped",
        "password": "e2e_scoped_pw",
        "group_ids": [
            (4, env.ref("base.group_user").id),
            (4, env.ref("analitix.group_manager").id),
        ],
    })
scoped.write({
    "password": "e2e_scoped_pw",
    "analitix_store_ids": [(6, 0, store.ids)],
})

# --- phase 5 and 7 roles, for the browser journeys ---------------------
def make_user(login, name, groups, **extra):
    user = Users.with_context(active_test=False).search(
        [("login", "=", login)], limit=1)
    vals = {
        "name": name,
        "login": login,
        "password": login + "_pw",
        "group_ids": [(4, env.ref("base.group_user").id)]
                     + [(4, env.ref(g).id) for g in groups],
    }
    vals.update(extra)
    if user:
        user.write(vals)
        return user
    return Users.with_context(no_reset_password=True).create(vals)


# Two of them, because the watch list needs a second pair of eyes: the person
# who adds an entry cannot be the one who confirms it, and that control is only
# really tested by driving it with two different logins.
officer_a = make_user("e2e_sec_a", "E2E Security A", ["analitix.group_security"])
officer_b = make_user("e2e_sec_b", "E2E Security B", ["analitix.group_security"])
store.write({
    "watchlist_enabled": True,
    "watchlist_min_liveness": 0.5,
    "watchlist_user_ids": [(6, 0, (officer_a | officer_b).ids)],
})

# A chain, so the console has a region to compare within, and a regional user
# who must not be able to reach outside it.
Brand = env["analitix.brand"].sudo()
Region = env["analitix.region"].sudo()
brand = Brand.search([("code", "=", "E2EB")], limit=1) or Brand.create({
    "name": "E2E Chain", "code": "E2EB", "company_id": env.company.id})
region = Region.search([("code", "=", "E2ER")], limit=1) or Region.create({
    "name": "E2E Region", "code": "E2ER", "brand_id": brand.id})
store.write({"brand_id": brand.id, "region_id": region.id})
regional = make_user("e2e_regional", "E2E Regional", ["analitix.group_regional"],
                     analitix_region_ids=[(6, 0, region.ids)])

# Close a few days so the console is not empty when the browser opens it.
Daily = env["analitix.store.daily"].sudo()
today = fields.Date.context_today(env.user)
for offset in range(3, 0, -1):
    Daily.roll_up(store, fields.Date.subtract(today, days=offset))

env.cr.commit()

print("E2E_JSON_START")
print(json.dumps({
    "store_id": store.id,
    "store_name": store.name,
    "device_uid": device.device_uid,
    "api_key": key,
    "other_store_id": other.id,
    "other_device_uid": other_device.device_uid,
    "other_api_key": other_key,
    "scoped_login": "e2e_scoped",
    "scoped_password": "e2e_scoped_pw",
    "security_a": "e2e_sec_a",
    "security_b": "e2e_sec_b",
    "regional_login": "e2e_regional",
}, indent=2))
print("E2E_JSON_END")
