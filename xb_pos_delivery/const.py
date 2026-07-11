# -*- coding: utf-8 -*-

# Supported delivery platforms. Extend with selection_add in bridge modules.
PROVIDERS = [
    ('uber_eats', 'Uber Eats'),
    ('didi_food', 'DiDi Food'),
]

# Normalized delivery order lifecycle (superset of both platforms).
DELIVERY_STATUSES = [
    ('placed', 'New'),
    ('accepted', 'Accepted'),
    ('ready', 'Ready'),
    ('dispatched', 'Dispatched'),
    ('delivered', 'Delivered'),
    ('cancelled', 'Cancelled'),
]

# Sequence used to prevent status regressions from late webhooks.
STATUS_SEQUENCE = {
    'placed': 1,
    'accepted': 2,
    'ready': 3,
    'dispatched': 4,
    'delivered': 5,
    'cancelled': 6,
}

DELIVERY_TYPES = [
    ('delivery', 'Delivery'),
    ('pickup', 'Pickup'),
]

# Journal short-code prefix per provider (journal code = prefix + config id).
JOURNAL_CODES = {
    'uber_eats': 'UBE',
    'didi_food': 'DDF',
}

# Bus notification types sent to the POS UI.
BUS_ORDER_EVENT = 'XB_DELIVERY_ORDER'
BUS_STORE_EVENT = 'XB_DELIVERY_STORE'
