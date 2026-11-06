# The XPago API. One address for both environments: the XPago key says which one (xpk_test_ charges nothing,
# xpk_live_ charges for real). The system parameter `xpago.api_url` points to another server (a local sandbox);
# never set in production.
API_URL = 'https://api.xpago.mx'
API_URL_PARAM = 'xpago.api_url'
KEY_PREFIXES = {'test': 'xpk_test_', 'enabled': 'xpk_live_'}
KEY_PREFIX = 'xpk_'

# Where a merchant connects its XPago account and gets its XPago key (a key that does not start with xpk_, as the one
# of a former XPago app, no longer charges). The system parameter `xpago.connect_url` points elsewhere.
CONNECT_URL = 'https://xpago.mx/conectar'
CONNECT_URL_PARAM = 'xpago.connect_url'

PAYMENT_RETURN_ROUTE = '/payment/xpago/return'
CARD_RETURN_ROUTE = '/payment/xpago/card/return'

# How long the customer has to save a card or pay in the card-saving checkout.
CARD_CHECKOUT_TTL_MINUTES = 60

# Visa, Mastercard and American Express, credit and debit.
DEFAULT_PAYMENT_METHOD_CODES = {'card', 'visa', 'mastercard', 'amex'}

# Status of a checkout (online store, links, invoices).
STATUS_MAPPING = {
    'pending': ('pending',),
    'done': ('paid', 'refunded'),
    'canceled': ('canceled', 'expired'),
}

# Months without interest XPago accepts on a checkout. 1 is the single payment.
MAX_TERMS = 24

# How long a pending payment is read back by the scheduled action: a checkout lives up to 48 hours.
SYNC_WINDOW_HOURS = 72

# Status of a payment on a saved card.
CARD_PAYMENT_STATUS = {
    'done': ('paid', 'refunded'),
    'authorized': ('held',),
    'canceled': ('released',),
    'error': ('failed',),
    'pending': ('pending',),
}
