# -*- coding: utf-8 -*-
"""Thin HTTP client for the Channex.io API.

Channex (https://channex.io) is a channel-manager aggregator: one API
gives two-way connectivity with Booking.com, Expedia, Airbnb, Agoda,
Vrbo and 100+ channels. Use https://staging.channex.io for the free
sandbox and https://app.channex.io in production.
"""
import logging

import requests

_logger = logging.getLogger(__name__)


class ChannexError(Exception):
    pass


class ChannexClient:
    def __init__(self, base_url, api_key, timeout=30):
        self.base_url = (base_url or "https://staging.channex.io").rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self):
        return {
            "user-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def _request(self, method, path, params=None, json=None):
        url = self.base_url + path
        try:
            resp = requests.request(
                method, url, params=params, json=json,
                headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise ChannexError("Channex %s %s failed: %s"
                               % (method, path, exc)) from exc
        if resp.status_code >= 400:
            raise ChannexError(
                "Channex %s %s → HTTP %s: %s"
                % (method, path, resp.status_code, resp.text[:500]))
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError as exc:
            raise ChannexError(
                "Channex %s %s: invalid JSON response" % (method, path)
            ) from exc

    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def post(self, path, json=None):
        return self._request("POST", path, json=json)
