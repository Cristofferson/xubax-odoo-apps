# API of the XPago processing platform. The provider's state chooses the environment: "Test mode" charges in the
# demo environment and "Enabled" in production.
API_URLS = {
    'test': 'https://demo-api-harmony.compago.com/api',
    'enabled': 'https://api-harmony.compago.com/api',
}

PAYMENT_RETURN_ROUTE = '/payment/xpago/return'

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
