import json
from unittest.mock import patch

import requests
from urllib3.exceptions import NewConnectionError, ProtocolError

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.xpago import const, failover
from odoo.addons.xpago.tests.common import XpagoCommon

MAIN, N1, N2, N3 = const.API_URLS


def _response(status, body=None, text=None):
    response = requests.models.Response()
    response.status_code = status
    response._content = (json.dumps(body) if body is not None else (text or '')).encode()
    response.headers['Content-Type'] = 'application/json' if body is not None else 'text/html'
    response.url = 'https://example'
    return response


def _no_connection():
    return requests.exceptions.ConnectionError(NewConnectionError(None, 'Connection refused'))


def _dropped():
    """The connection broke after the request left: it may have been served."""
    return requests.exceptions.ConnectionError(ProtocolError('Connection aborted.', ConnectionResetError()))


class Calls:
    """A fake requests.request: answers (or raises) by address, in order, and records every call."""

    def __init__(self, **by_host):
        self.by_host = {host: list(answers) for host, answers in by_host.items()}
        self.calls = []

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs.get('headers') or {}))
        host = url.split('/')[2].split('.')[0]
        answer = self.by_host[host].pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    @property
    def hosts(self):
        return [url.split('/')[2].split('.')[0] for _method, url, _headers in self.calls]


@tagged('post_install', '-at_install')
class TestFailover(XpagoCommon):

    def setUp(self):
        super().setUp()
        failover.forget()
        self.addCleanup(failover.forget)
        self.ok = _response(200, {'id': 'x'})

    def send(self, calls, method='GET', key=None):
        headers = {'Idempotency-Key': key} if key else {}
        return failover.send(method, list(const.API_URLS), '/v1/account', memo_key='db', headers=headers,
                             request=calls, sleep=lambda _s: None)

    def test_the_main_address_first(self):
        calls = Calls(api=[self.ok])
        response, url = self.send(calls)
        self.assertEqual((response.status_code, url), (200, MAIN + '/v1/account'))
        self.assertEqual(calls.hosts, ['api'])

    def test_no_connection_goes_to_the_next_address(self):
        calls = Calls(api=[_no_connection()], n1=[requests.exceptions.ConnectTimeout()], n2=[self.ok])
        _response_, url = self.send(calls, 'POST', key='k-1')
        self.assertEqual(url, N2 + '/v1/account')
        self.assertEqual(calls.hosts, ['api', 'n1', 'n2'])
        # The same Idempotency-Key on every address.
        self.assertEqual({headers['Idempotency-Key'] for _m, _u, headers in calls.calls}, {'k-1'})

    def test_tls_failure_goes_to_the_next_address(self):
        calls = Calls(api=[requests.exceptions.SSLError()], n1=[self.ok])
        self.assertEqual(self.send(calls, 'POST', key='k')[1], N1 + '/v1/account')

    def test_standby_node_goes_to_the_next_address(self):
        standby = _response(503, {'error': {'code': 'node_standby', 'message': 'replica'}})
        calls = Calls(api=[standby], n1=[self.ok])
        self.assertEqual(self.send(calls, 'POST', key='k')[1], N1 + '/v1/account')

    def test_cloudflare_without_an_xpago_answer_goes_to_the_next_address(self):
        for status in (521, 522, 530):
            failover.forget()
            calls = Calls(api=[_response(status, text='<html>Cloudflare</html>')], n1=[self.ok])
            self.assertEqual(self.send(calls)[1], N1 + '/v1/account', status)

    def test_answers_of_xpago_are_never_retried_elsewhere(self):
        for answer in (_response(400, {'error': {'code': 'invalid_request'}}),
                       _response(401, {'error': {'code': 'unauthorized'}}),
                       _response(409, {'error': {'code': 'request_in_progress'}}),
                       _response(502, {'error': {'code': 'processor_unavailable'}}),
                       _response(503, {'error': {'code': 'processor_unavailable'}}),
                       _response(520, {'error': {'code': 'processor_error'}}),
                       _response(500, text='boom')):
            failover.forget()
            calls = Calls(api=[answer])
            response, url = self.send(calls, 'POST', key='k')
            self.assertEqual((response.status_code, calls.hosts), (answer.status_code, ['api']))

    def test_post_without_answer_in_time_is_retried_on_the_same_address_only(self):
        calls = Calls(api=[requests.exceptions.ReadTimeout(), self.ok])
        response, url = self.send(calls, 'POST', key='k-2')
        self.assertEqual((response.status_code, calls.hosts), (200, ['api', 'api']))
        self.assertEqual([headers['Idempotency-Key'] for _m, _u, headers in calls.calls], ['k-2', 'k-2'])

    def test_post_without_answer_twice_is_an_unknown_outcome(self):
        calls = Calls(api=[requests.exceptions.ReadTimeout(), requests.exceptions.ReadTimeout()], n1=[self.ok])
        with self.assertRaises(failover.OutcomeUnknown):
            self.send(calls, 'POST', key='k-3')
        self.assertEqual(calls.hosts, ['api', 'api'])

    def test_post_dropped_midway_is_not_sent_elsewhere(self):
        calls = Calls(api=[_dropped(), _dropped()], n1=[self.ok])
        with self.assertRaises(failover.OutcomeUnknown):
            self.send(calls, 'POST', key='k-4')
        self.assertEqual(calls.hosts, ['api', 'api'])

    def test_post_without_idempotency_key_is_not_resent(self):
        calls = Calls(api=[requests.exceptions.ReadTimeout()], n1=[self.ok])
        with self.assertRaises(failover.OutcomeUnknown):
            self.send(calls, 'POST')
        self.assertEqual(calls.hosts, ['api'])

    def test_get_without_answer_in_time_goes_to_the_next_address(self):
        calls = Calls(api=[requests.exceptions.ReadTimeout()], n1=[self.ok])
        self.assertEqual(self.send(calls)[1], N1 + '/v1/account')

    def test_nobody_answers(self):
        calls = Calls(api=[_no_connection()], n1=[_no_connection()], n2=[_no_connection()], n3=[_no_connection()])
        with self.assertRaises(failover.Unreachable):
            self.send(calls, 'POST', key='k')
        self.assertEqual(calls.hosts, ['api', 'n1', 'n2', 'n3'])

    def test_the_backup_that_worked_goes_first_for_a_while(self):
        self.send(Calls(api=[_no_connection()], n1=[self.ok]))
        calls = Calls(n1=[self.ok])
        self.send(calls)
        self.assertEqual(calls.hosts, ['n1'])
        # After a while, the main address again.
        with patch.object(failover.time, 'monotonic', return_value=failover.time.monotonic() + 301):
            calls = Calls(api=[self.ok])
            self.send(calls)
        self.assertEqual(calls.hosts, ['api'])

    def test_addresses_from_the_system_parameters(self):
        params = self.env['ir.config_parameter'].sudo()
        self.assertEqual(self.provider._xpago_api_urls(), list(const.API_URLS))
        params.set_param(const.API_URLS_PARAM, ' https://a.example/ , https://b.example ')
        self.assertEqual(self.provider._xpago_api_urls(), ['https://a.example', 'https://b.example'])
        params.set_param(const.API_URL_PARAM, 'http://127.0.0.1:8077/')
        self.assertEqual(self.provider._xpago_api_urls(), ['http://127.0.0.1:8077'])

    def test_provider_requests_go_through_the_list(self):
        calls = Calls(api=[_no_connection()], n1=[_response(200, {'name': 'Taqueria'})])
        with patch.object(failover.requests, 'request', calls):
            self.assertEqual(self._xpago_call('GET', '/v1/account'), {'name': 'Taqueria'})
        self.assertEqual(calls.hosts, ['api', 'n1'])

    def test_provider_says_when_nobody_answers_or_the_outcome_is_unknown(self):
        calls = Calls(**{host: [_no_connection()] for host in ('api', 'n1', 'n2', 'n3')})
        with patch.object(failover.requests, 'request', calls), self.assertRaises(ValidationError) as caught:
            self._xpago_call('GET', '/v1/account')
        self.assertIn('XPago', str(caught.exception))
        calls = Calls(api=[requests.exceptions.ReadTimeout(), requests.exceptions.ReadTimeout()])
        with patch.object(failover.requests, 'request', calls), patch.object(failover.time, 'sleep'), \
                self.assertRaises(ValidationError) as caught:
            self._xpago_call('POST', '/v1/terminal-charges', json={}, idempotency_key='k')
        self.assertIn('may have gone through', str(caught.exception))

    def _xpago_call(self, method, endpoint, json=None, idempotency_key=None):
        return self.provider._xpago_make_request(method, endpoint, json=json, idempotency_key=idempotency_key)
