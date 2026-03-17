from __future__ import annotations

import json
from urllib import error, request

from ..parse_updates import infer_company, infer_period, summarize
from .base import ParsedUpdateResult


class BemParseProvider:
    name = 'bem'

    def __init__(self, settings) -> None:
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
        }
        if self.settings.bem_api_key:
            headers['Authorization'] = f'Bearer {self.settings.bem_api_key}'
        return headers

    def _build_payload(self, raw: dict) -> dict:
        combined_text = '\n\n'.join(
            part for part in [raw.get('body_text') or '', raw.get('attachment_text') or ''] if part
        )
        return {
            'input': {
                'gmail_message_id': raw.get('gmail_message_id'),
                'subject': raw.get('subject'),
                'from_address': raw.get('from_address'),
                'received_at': raw.get('received_at'),
                'body_text': raw.get('body_text') or '',
                'attachment_text': raw.get('attachment_text') or '',
                'combined_text': combined_text,
            },
            'schema': {
                'type': 'object',
                'properties': {
                    'company_name_raw': {'type': ['string', 'null']},
                    'reporting_period_raw': {'type': ['string', 'null']},
                    'summary': {'type': ['string', 'null']},
                    'highlights': {'type': 'array', 'items': {'type': 'string'}},
                    'asks': {'type': 'array', 'items': {'type': 'string'}},
                    'risks': {'type': 'array', 'items': {'type': 'string'}},
                    'metrics': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'name_raw': {'type': ['string', 'null']},
                                'canonical_name': {'type': ['string', 'null']},
                                'value_raw': {'type': ['string', 'null']},
                                'value_type': {'type': ['string', 'null']},
                                'numeric_value': {'type': ['number', 'null']},
                                'unit': {'type': ['string', 'null']},
                                'period': {'type': ['string', 'null']},
                                'confidence': {'type': ['number', 'null']},
                                'source_excerpt': {'type': ['string', 'null']},
                            },
                        },
                    },
                },
            },
        }

    def _call_bem(self, payload: dict) -> dict:
        if not self.settings.bem_api_url:
            raise ValueError('BEM_API_URL is not set')
        body = json.dumps(payload).encode('utf-8')
        req = request.Request(
            self.settings.bem_api_url,
            data=body,
            headers=self._headers(),
            method='POST',
        )
        timeout = self.settings.bem_timeout_seconds or 60
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except error.HTTPError as e:
            details = e.read().decode('utf-8', errors='replace')
            raise RuntimeError(f'bem API error {e.code}: {details}') from e
        except error.URLError as e:
            raise RuntimeError(f'bem API request failed: {e}') from e

    def _normalize_bem_output(self, raw: dict, response: dict) -> dict:
        extracted = response.get('output') or response.get('result') or response
        metrics_json: dict[str, dict] = {}
        confidence_json: dict[str, dict] = {}
        for metric in extracted.get('metrics', []) or []:
            key = metric.get('canonical_name') or metric.get('name_raw')
            if not key:
                continue
            key = str(key).strip().lower().replace(' ', '_')
            numeric_value = metric.get('numeric_value')
            value = numeric_value if numeric_value is not None else metric.get('value_raw')
            metrics_json[key] = {
                'value': value,
                'unit': metric.get('unit'),
                'period': metric.get('period'),
                'value_type': metric.get('value_type'),
                'value_raw': metric.get('value_raw'),
                'source_excerpt': metric.get('source_excerpt'),
            }
            confidence_json[key] = {
                'confidence': metric.get('confidence'),
                'source': 'bem',
            }

        period = infer_period(raw.get('subject'), extracted.get('reporting_period_raw') or raw.get('body_text') or '')
        return {
            'gmail_message_id': raw.get('gmail_message_id'),
            'gmail_thread_id': raw.get('gmail_thread_id'),
            'company_name': extracted.get('company_name_raw') or infer_company(raw.get('subject'), raw.get('body_text')),
            'subject': raw.get('subject'),
            'from_address': raw.get('from_address'),
            'to_addresses': raw.get('to_addresses', []),
            'received_at': raw.get('received_at'),
            **period,
            'summary': extracted.get('summary') or summarize((raw.get('body_text') or '')[:4000]),
            'metrics_json': metrics_json,
            'highlights_json': extracted.get('highlights', []) or [],
            'asks_json': extracted.get('asks', []) or [],
            'risks_json': extracted.get('risks', []) or [],
            'people_json': [],
            'confidence_json': confidence_json,
            'source_path': raw.get('source_path'),
            'parser_version': 'bem-v1',
            'parser_provider': self.name,
        }

    def parse(self, raw: dict) -> ParsedUpdateResult:
        payload = self._build_payload(raw)
        response = self._call_bem(payload)
        update = self._normalize_bem_output(raw, response)
        return ParsedUpdateResult(update=update, provider_output=response)
