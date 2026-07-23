# -*- coding: utf-8 -*-
"""Find a picture for a product that has none.

Two back ends are provided. DuckDuckGo needs no credentials at all, which is
what makes the feature usable out of the box; Google Programmable Search is
there for those who already pay for a key. Adding another engine means adding
one ``_search_<name>`` method and one selection value.

The search never runs during a bill import: it is triggered by the user or by
the scheduled action, so importing a bill never waits on the internet.
"""
import base64
import json
import logging
import re
from urllib.parse import urlparse

import requests

from odoo import api, models
from odoo.tools.image import ImageProcess, image_process

_logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
TIMEOUT = 20
MAX_BYTES = 8 * 1024 * 1024
# Bills are read in batches; keep a single cron run bounded.
CRON_BATCH = 40


class XbProductImageFinder(models.AbstractModel):
    _name = 'xb.product.image.finder'
    _description = "Product Image Finder"

    # ------------------------------------------------------------------
    # Search engines
    # ------------------------------------------------------------------
    @api.model
    def _search_images(self, query, limit, company):
        provider = company.sudo().xb_vbp_image_provider or 'duckduckgo'
        method = getattr(self, '_search_%s' % provider, None)
        if not method:
            _logger.warning("Unknown image provider %r", provider)
            return []
        try:
            return method(query, limit, company)
        except Exception as err:  # noqa: BLE001 - never break a business flow
            _logger.warning("Image search failed for %r: %s", query, err)
            return []

    @api.model
    def _search_duckduckgo(self, query, limit, company):
        """DuckDuckGo hands out images through an internal endpoint that first
        requires a one-shot token (``vqd``) obtained from the HTML page."""
        session = requests.Session()
        session.headers.update({'User-Agent': USER_AGENT})
        page = session.post(
            'https://duckduckgo.com/', data={'q': query}, timeout=TIMEOUT)
        page.raise_for_status()
        match = re.search(r'vqd=["\']?([\d-]+)["\']?', page.text)
        if not match:
            _logger.info("DuckDuckGo did not return a token for %r", query)
            return []
        response = session.get(
            'https://duckduckgo.com/i.js',
            params={
                'l': 'us-en',
                'o': 'json',
                'q': query,
                'vqd': match.group(1),
                'f': ',,,',
                'p': '1',
            },
            headers={'Referer': 'https://duckduckgo.com/'},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return []
        results = []
        for item in (payload.get('results') or [])[:limit * 3]:
            results.append({
                'url': item.get('image'),
                'name': item.get('title'),
                # The engine reports its own index here ("Bing"), which tells
                # the reviewer nothing. The site the picture lives on does.
                'source': self._url_host(item.get('url')) or item.get('source'),
                'width': int(item.get('width') or 0),
                'height': int(item.get('height') or 0),
            })
        return results

    @api.model
    def _url_host(self, url):
        if not url:
            return False
        try:
            host = urlparse(url).netloc
        except ValueError:
            return False
        return host[4:] if host.startswith('www.') else host

    @api.model
    def _search_google_cse(self, query, limit, company):
        company = company.sudo()
        if not company.xb_vbp_image_google_key or not company.xb_vbp_image_google_cx:
            _logger.info("Google image search is selected but not configured.")
            return []
        response = requests.get(
            'https://www.googleapis.com/customsearch/v1',
            params={
                'key': company.xb_vbp_image_google_key,
                'cx': company.xb_vbp_image_google_cx,
                'q': query,
                'searchType': 'image',
                'num': min(max(limit, 1), 10),
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        results = []
        for item in payload.get('items') or []:
            image = item.get('image') or {}
            results.append({
                'url': item.get('link'),
                'name': item.get('title'),
                'source': self._url_host(image.get('contextLink')),
                'width': int(image.get('width') or 0),
                'height': int(image.get('height') or 0),
            })
        return results

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------
    @api.model
    def _download_image(self, url, min_px=0):
        """Fetch, validate and normalise one candidate.

        Returns the base64 payload, the width and the height, or ``None`` when
        the file is not a usable image.
        """
        if not url or not url.lower().startswith(('http://', 'https://')):
            return None
        try:
            response = requests.get(
                url,
                headers={'User-Agent': USER_AGENT},
                timeout=TIMEOUT,
                stream=True,
            )
            response.raise_for_status()
            content = b''
            for chunk in response.iter_content(65536):
                content += chunk
                if len(content) > MAX_BYTES:
                    return None
        except Exception as err:  # noqa: BLE001
            _logger.debug("Could not download %s: %s", url, err)
            return None
        if not content:
            return None
        try:
            processed = ImageProcess(content, verify_resolution=False)
            if not processed.image:
                return None
            width, height = processed.image.size
            if min_px and min(width, height) < min_px:
                return None
            normalised = image_process(content, size=(1920, 1920))
        except Exception as err:  # noqa: BLE001
            _logger.debug("Could not process %s: %s", url, err)
            return None
        return base64.b64encode(normalised), width, height

    # ------------------------------------------------------------------
    # Filling candidates
    # ------------------------------------------------------------------
    @api.model
    def _build_query(self, label, company):
        query = ' '.join((label or '').split())
        suffix = company.sudo().xb_vbp_image_query_suffix
        if suffix:
            query = '%s %s' % (query, suffix)
        return query.strip()

    @api.model
    def _collect_candidates(self, label, company):
        company = company.sudo()
        wanted = max(company.xb_vbp_image_candidates or 6, 1)
        min_px = company.xb_vbp_image_min_px or 0
        query = self._build_query(label, company)
        if not query:
            return []
        found = []
        for result in self._search_images(query, wanted, company):
            if len(found) >= wanted:
                break
            if result.get('width') and min_px and min(
                    result['width'], result.get('height') or 0) < min_px:
                continue
            downloaded = self._download_image(result.get('url'), min_px=min_px)
            if not downloaded:
                continue
            payload, width, height = downloaded
            found.append({
                'name': (result.get('name') or '')[:200] or False,
                'url': result['url'],
                'source': (result.get('source') or '')[:200] or False,
                'width': width,
                'height': height,
                'image_1920': payload,
                'sequence': len(found) * 10,
            })
        return found

    @api.model
    def _fill_candidates_for_proposals(self, proposals, force=False):
        for proposal in proposals:
            company = proposal.company_id
            if company.sudo().xb_vbp_image_mode == 'off' and not force:
                continue
            proposal.image_candidate_ids.unlink()
            candidates = self._collect_candidates(proposal.name, company)
            if not candidates:
                proposal.sudo().image_state = 'failed'
                continue
            proposal.sudo().write({
                'image_candidate_ids': [(0, 0, vals) for vals in candidates],
                'image_state': 'proposed',
            })
            if company.sudo().xb_vbp_image_mode == 'auto':
                proposal.image_candidate_ids[:1].action_choose()
        return True

    @api.model
    def _fill_candidates_for_templates(self, templates, force=False):
        for template in templates:
            company = template.company_id or self.env.company
            if company.sudo().xb_vbp_image_mode == 'off' and not force:
                continue
            template.xb_vbp_image_candidate_ids.unlink()
            candidates = self._collect_candidates(template.name, company)
            if not candidates:
                template.sudo().xb_vbp_image_state = 'failed'
                continue
            template.sudo().write({
                'xb_vbp_image_candidate_ids': [(0, 0, vals) for vals in candidates],
                'xb_vbp_image_state': 'proposed',
            })
            if company.sudo().xb_vbp_image_mode == 'auto':
                template.xb_vbp_image_candidate_ids[:1].action_choose()
        return True

    # ------------------------------------------------------------------
    # Scheduled action
    # ------------------------------------------------------------------
    @api.model
    def _cron_fetch_images(self, batch=CRON_BATCH):
        companies = self.env['res.company'].sudo().search(
            [('xb_vbp_image_mode', '!=', 'off')])
        if not companies:
            return True
        proposals = self.env['xb.bill.product.proposal'].sudo().search(
            [
                ('image_state', '=', 'pending'),
                ('state', '=', 'draft'),
                ('company_id', 'in', companies.ids),
            ],
            limit=batch,
        )
        if proposals:
            self._fill_candidates_for_proposals(proposals)
        remaining = batch - len(proposals)
        if remaining > 0:
            templates = self.env['product.template'].sudo().search(
                [
                    ('xb_vbp_image_state', '=', 'pending'),
                    ('image_1920', '=', False),
                    '|',
                    ('company_id', 'in', companies.ids),
                    ('company_id', '=', False),
                ],
                limit=remaining,
            )
            if templates:
                self._fill_candidates_for_templates(templates)
        _logger.info(
            "Vendor bill products: image search processed %s proposal(s).",
            len(proposals))
        return True
