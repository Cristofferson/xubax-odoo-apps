# -*- coding: utf-8 -*-
"""Provider driver framework.

A driver wraps the HTTP API of one delivery platform. Drivers are plain
Python classes instantiated per request with a (sudoed) ``xb.delivery.account``
record. They convert between the provider payloads and the neutral
structures used by the module:

* menu snapshot (``account._build_menu_snapshot()``) -> provider menu payload
* provider order payload -> normalized order dict (see ``parse_order``)

Normalized order dict::

    {
        'external_id': str,          # platform order id
        'display_id': str,           # short id shown to customer/courier
        'type': 'delivery'|'pickup',
        'note': str,
        'prep_time': int|None,       # minutes
        'cash_due': float,           # > 0 on cash orders
        'customer': {'name', 'phone', 'email', 'street', 'city', 'zip'},
        'items': [{'ref', 'name', 'qty', 'unit_price',   # tax incl, options incl
                   'options': [{'ref', 'name', 'qty', 'price'}], 'note'}],
        'charges': [{'type': 'delivery'|'packaging'|'tip'|'other',
                     'name', 'amount'}],                  # restaurant revenue only
        'discounts': [{'title', 'code', 'amount', 'restaurant_funded': bool}],
        'raw': dict,                 # original payload
    }
"""
import logging

import requests

_logger = logging.getLogger(__name__)

_DRIVER_REGISTRY = {}


def register_driver(provider):
    def decorator(cls):
        _DRIVER_REGISTRY[provider] = cls
        cls.provider = provider
        return cls
    return decorator


def get_driver_class(provider):
    return _DRIVER_REGISTRY.get(provider)


class DeliveryDriverError(Exception):
    """Raised on any provider API error; message is user-displayable."""


class BaseDeliveryDriver:
    """Interface every provider driver implements."""

    provider = None
    TIMEOUT = 20

    def __init__(self, account):
        self.account = account
        self.env = account.env

    # -- HTTP helper ---------------------------------------------------

    def _request(self, method, url, log_event=None, **kwargs):
        kwargs.setdefault('timeout', self.TIMEOUT)
        try:
            response = requests.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise DeliveryDriverError(
                'Network error calling %s: %s' % (url, exc)) from exc
        if log_event:
            self.account._log(
                'out', log_event,
                payload={'url': url, 'status': response.status_code,
                         'body': response.text[:2000]},
                success=response.ok)
        return response

    # -- Interface ------------------------------------------------------

    def test_connection(self):
        """Validate credentials; return a human message or raise."""
        raise NotImplementedError()

    def push_menu(self, snapshot):
        """Publish the neutral menu snapshot; return a result message."""
        raise NotImplementedError()

    def set_store_status(self, online):
        raise NotImplementedError()

    def set_item_availability(self, template, available):
        raise NotImplementedError()

    def accept_order(self, order):
        raise NotImplementedError()

    def deny_order(self, order, reason):
        raise NotImplementedError()

    def mark_ready(self, order):
        """Optional: notify the platform the food is ready."""
        return True

    def verify_webhook(self, headers, raw_body):
        """Return True when the webhook signature is authentic."""
        raise NotImplementedError()

    def parse_order(self, payload):
        """Convert a provider order payload into the normalized dict."""
        raise NotImplementedError()
