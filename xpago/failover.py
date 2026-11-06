"""The XPago API answers on several addresses: the main one goes through Cloudflare, the others reach the XPago nodes
straight, for when Cloudflare is down. They are tried in order, and the next one only when the request surely was not
served (deploy/ha/odoo-app-failover.md of the XPago gateway):

- the connection never happened (DNS, refused, TLS, connect timeout);
- the node answered 503 ``node_standby`` (it is not the primary and refused before doing anything);
- Cloudflare answered 52x/530 without an XPago body (it could not reach the node).

Any other answer is XPago's and goes back as it is. A POST whose answer did not arrive in time may have charged: it is
sent once more to the same address with the same Idempotency-Key (the gateway gives back the first answer), and if
that one does not arrive either, the outcome is unknown and nobody sends it again blindly.

Plain Python, without Odoo, so every version of the app shares it as it is."""

import threading
import time

import requests
from urllib3.exceptions import ConnectTimeoutError, NewConnectionError

try:  # urllib3 2 tells a DNS failure apart; in urllib3 1 it is a NewConnectionError
    from urllib3.exceptions import NameResolutionError
except ImportError:
    NameResolutionError = NewConnectionError

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 15
# A POST may wait for the terminal or the processor.
POST_READ_TIMEOUT = 30
MAX_ATTEMPTS = 4
# After a backup address worked, start with it for a while instead of losing seconds on the main one at every call;
# then go back to the main one, so the traffic returns to Cloudflare once it is back.
REMEMBER_SECONDS = 300
RETRY_WAIT_SECONDS = 2

CLOUDFLARE_STATUSES = frozenset(range(520, 528)) | {530}

_last_good = {}
_lock = threading.Lock()


class Unreachable(Exception):
    """None of the addresses served the request."""


class OutcomeUnknown(Exception):
    """A POST may or may not have been served: look the operation up before sending it again."""


def _xpago_error_code(response):
    try:
        body = response.json()
    except ValueError:
        return None
    if isinstance(body, dict) and isinstance(body.get('error'), dict):
        return body['error'].get('code') or ''
    return None


def is_failover_response(response):
    """Whether this answer means the request was not served, so the next address may get it."""
    if response.status_code == 503:
        return _xpago_error_code(response) == 'node_standby'
    if response.status_code in CLOUDFLARE_STATUSES:
        return _xpago_error_code(response) is None
    return False


def _never_sent(error):
    """Whether a connection error happened before the request left (so another node can safely get it)."""
    if isinstance(error, (requests.exceptions.ConnectTimeout, requests.exceptions.SSLError)):
        return True
    reason = error.args[0] if error.args else None
    reason = getattr(reason, 'reason', reason)
    return isinstance(reason, (NewConnectionError, NameResolutionError, ConnectTimeoutError))


def ordered(urls, memo_key):
    """The addresses to try, starting with the one that worked lately when it is not the main one."""
    now = time.monotonic()
    with _lock:
        good = _last_good.get(memo_key)
        if good and good[1] <= now:
            _last_good.pop(memo_key, None)
            good = None
    if good and good[0] in urls:
        return [good[0]] + [url for url in urls if url != good[0]]
    return list(urls)


def remember(memo_key, url, main_url):
    with _lock:
        if url == main_url:
            _last_good.pop(memo_key, None)
        else:
            _last_good[memo_key] = (url, time.monotonic() + REMEMBER_SECONDS)


def forget(memo_key=None):
    with _lock:
        if memo_key is None:
            _last_good.clear()
        else:
            _last_good.pop(memo_key, None)


def send(method, urls, endpoint, *, memo_key, headers=None, params=None, json=None, data=None,
         request=None, sleep=None):
    """Send the request to the first address that serves it.

    :return: (response, url) of the address that answered.
    :raise Unreachable: when no address served it.
    :raise OutcomeUnknown: when a POST may have been served but its answer never came."""
    request = request or requests.request
    sleep = sleep or time.sleep
    method = method.upper()
    read_timeout = POST_READ_TIMEOUT if method == 'POST' else READ_TIMEOUT
    candidates = ordered([url.rstrip('/') for url in urls if url], memo_key)[:MAX_ATTEMPTS]
    last_error = None
    for base in candidates:
        url = base + endpoint
        response = None
        for attempt in range(2):
            try:
                response = request(method, url, params=params, json=json, data=data, headers=headers,
                                   timeout=(CONNECT_TIMEOUT, read_timeout))
                break
            except requests.exceptions.RequestException as error:
                last_error = error
                if method != 'POST':
                    break  # nothing was charged: the next address may get it
                if isinstance(error, requests.exceptions.ConnectionError) and _never_sent(error):
                    break
                # The POST may have arrived: the same address once more, with the same Idempotency-Key.
                if attempt == 0 and (headers or {}).get('Idempotency-Key'):
                    sleep(RETRY_WAIT_SECONDS)
                    continue
                raise OutcomeUnknown(str(error)) from error
        if response is None:
            continue
        if is_failover_response(response):
            last_error = f'{url} answered {response.status_code}'
            continue
        remember(memo_key, base, urls[0].rstrip('/'))
        return response, url
    raise Unreachable(str(last_error))
