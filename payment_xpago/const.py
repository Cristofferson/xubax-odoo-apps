# API of the XPago processing platform. The provider's live mode chooses the environment: out of live mode it
# charges in the demo environment, in live mode in production.
API_URLS = {
    'test': 'https://demo-api-harmony.compago.com/api',
    'live': 'https://api-harmony.compago.com/api',
}

PAYMENT_RETURN_ROUTE = '/payment/xpago/return'
CARD_RETURN_ROUTE = '/payment/xpago/card/return'

# How long the customer has to save a card or pay in the card-saving checkout.
CARD_CHECKOUT_TTL_MINUTES = 60

# Visa, Mastercard and American Express, credit and debit.
DEFAULT_PAYMENT_METHOD_CODES = {'card', 'visa', 'mastercard', 'amex'}

# Status of a one-time payment, as XPago reports it.
STATUS_MAPPING = {
    'pending': ('PENDING',),
    'done': ('CONFIRMED',),
    'canceled': ('CANCELLED',),
}

# Months without interest XPago accepts on a checkout. 1 is the single payment.
MAX_TERMS = 24

# How long a pending payment is read back by the scheduled action: a checkout lives up to 48 hours.
SYNC_WINDOW_HOURS = 72

# Status of a payment on a saved card.
CARD_PAYMENT_STATUS = {
    'done': ('CONFIRMED', 'REFUNDED'),
    'authorized': ('HELD',),
    'canceled': ('HOLD_RELEASED', 'HOLD_EXPIRED'),
    'error': ('CANCELLED',),
    'pending': ('PENDING', 'NOT_INITIALIZED'),
}
