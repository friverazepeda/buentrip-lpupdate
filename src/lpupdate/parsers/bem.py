from __future__ import annotations

import json
import base64
import time
import os
from pathlib import Path
from typing import Any
from urllib import error, request

from ..parse_updates import infer_company, infer_period, summarize
from .base import ParsedUpdateResult


class BemParseProvider:
    name = 'bem'

    def __init__(self, settings) -> None:
        self.settings = settings
        self._schema_cache: dict[str, Any] | None = None

    # ---------------------------------------------------------------------
    # Payload helpers
    # ---------------------------------------------------------------------
    def _schema_paths(self) -> list[Path]:
        paths: list[Path] = []
        override = getattr(self.settings, 'bem_schema_path', None) or os.getenv('BEM_SCHEMA_PATH')
        if override:
            paths.append(Path(override))
        paths.append(Path(__file__).with_name('bem_schema.json'))
        root_candidate = Path(__file__).resolve()
        if len(root_candidate.parents) >= 4:
            paths.append(root_candidate.parents[3] / 'bem_schema.json')
        return paths

    def _load_schema(self) -> dict[str, Any]:
        if self._schema_cache is not None:
            return self._schema_cache
        for path in self._schema_paths():
            if path and path.exists():
                self._schema_cache = json.loads(path.read_text())
                break
        if self._schema_cache is None:
            raise FileNotFoundError('bem schema not found; set BEM_SCHEMA_PATH or place bem_schema.json next to bem.py')
        return self._schema_cache

    def _headers(self) -> dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
        }
        if self.settings.bem_api_key:
            # v2 API uses x-api-key instead of Bearer token
            headers['x-api-key'] = self.settings.bem_api_key
        return headers

    def _build_payload(self, raw: dict) -> dict:
        body_text = raw.get('body_text') or ''
        attachment_text = raw.get('attachment_text') or ''
        header_lines = [
            f"Subject: {raw.get('subject') or ''}",
            f"From: {raw.get('from_address') or ''}",
            f"Received: {raw.get('received_at') or ''}",
            f"Gmail-Message-Id: {raw.get('gmail_message_id') or ''}",
        ]
        header_text = '\n'.join(line for line in header_lines if line and not line.endswith(': '))
        combined_parts = [header_text, body_text]
        if attachment_text:
            combined_parts.append('--- ATTACHMENTS ---')
            combined_parts.append(attachment_text)
        combined_text = '\n\n'.join(part for part in combined_parts if part)

        encoded_content = base64.b64encode(combined_text.encode('utf-8')).decode('ascii') if combined_text else ''
        single_file = {
            'inputType': 'text',
            'inputEncoding': 'base64',
            'inputContent': encoded_content,
        }

        workflow_name = getattr(self.settings, 'bem_workflow_name', None)
        if workflow_name:
            return {
                'calls': [
                    {
                        'workflowName': workflow_name,
                        'input': {
                            'singleFile': single_file,
                        },
                    }
                ]
            }

        function_name = getattr(self.settings, 'bem_function_name', None) or 'Parse-email-update'
        return {
            'calls': [
                {
                    'functionName': function_name,
                    'input': {
                        'singleFile': single_file,
                    },
                    'schema': self._load_schema(),
                }
            ]
        }

    def _call_bem(self, payload: dict) -> dict:
        api_url = self._api_url()

        body = json.dumps(payload).encode('utf-8')
        req = request.Request(
            api_url,
            data=body,
            headers=self._headers(),
            method='POST',
        )
        timeout = getattr(self.settings, 'bem_timeout_seconds', 60)
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except error.HTTPError as e:
            details = e.read().decode('utf-8', errors='replace')
            raise RuntimeError(f'bem API error {e.code}: {details}') from e
        except error.URLError as e:
            raise RuntimeError(f'bem API request failed: {e}') from e

        return self._await_calls(data)

    def _api_url(self) -> str:
        api_url = getattr(self.settings, 'bem_api_url', None)
        if not api_url or 'v1' in api_url:
            api_url = 'https://api.bem.ai/v2/calls'
        return api_url

    def _await_calls(self, response: dict) -> dict:
        calls = response.get('calls')
        if not calls:
            return response
        resolved: list[dict[str, Any]] = []
        for call in calls:
            status = (call.get('status') or '').lower()
            if status in {'running', 'queued', 'pending'}:
                call_id = call.get('callID')
                if call_id:
                    call = self._poll_call(call_id)
            resolved.append(call)
        response['calls'] = resolved
        return response

    def _poll_call(self, call_id: str) -> dict:
        poll_url = f"{self._api_url().rstrip('/')}/{call_id}"
        timeout_window = getattr(self.settings, 'bem_poll_timeout_seconds', 180)
        interval = getattr(self.settings, 'bem_poll_interval_seconds', 3)
        deadline = time.time() + timeout_window
        last_error: Exception | None = None
        while time.time() < deadline:
            req = request.Request(poll_url, headers=self._headers())
            try:
                with request.urlopen(req, timeout=getattr(self.settings, 'bem_timeout_seconds', 60)) as resp:
                    payload = json.loads(resp.read().decode('utf-8'))
            except Exception as exc:
                last_error = exc
                time.sleep(interval)
                continue
            call = payload.get('call') or (payload.get('calls') or [{}])[0]
            status = (call.get('status') or '').lower()
            if status in {'completed', 'succeeded', 'success'}:
                return call
            if status in {'failed', 'error', 'cancelled'}:
                raise RuntimeError(f"bem workflow {call_id} failed: {call.get('outputs') or call.get('error') or status}")
            time.sleep(interval)
        if last_error is not None:
            raise RuntimeError(f'bem workflow {call_id} polling failed: {last_error}')
        raise TimeoutError(f'bem workflow {call_id} did not finish before timeout')

    # ---------------------------------------------------------------------
    # Normalization helpers
    # ---------------------------------------------------------------------
    def _extract_result(self, response: dict) -> dict:
        def _from_outputs(container: dict[str, Any]) -> dict | None:
            outputs = container.get('outputs') or []
            for output in outputs:
                content = output.get('transformedContent') or output.get('output')
                if content:
                    return content
            return None

        if 'calls' in response and isinstance(response['calls'], list) and response['calls']:
            call_data = response['calls'][0]
            extracted = _from_outputs(call_data)
            if extracted is not None:
                return extracted
            return call_data.get('transformedContent') or call_data.get('output') or {}
        if 'call' in response and isinstance(response['call'], dict):
            call_payload = response['call']
            extracted = _from_outputs(call_payload)
            if extracted is not None:
                return extracted
            fcalls = call_payload.get('functionCalls') or []
            if fcalls:
                return fcalls[0].get('transformedContent') or fcalls[0].get('output') or {}
        return response.get('output') or response.get('result') or response

    def _normalize_metrics(self, payload: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        metrics_json: dict[str, Any] = {}
        confidence_json: dict[str, Any] = {}
        if isinstance(payload, dict):
            metrics_iter = [payload]
        elif isinstance(payload, list):
            metrics_iter = [item for item in payload if isinstance(item, dict)]
        else:
            metrics_iter = []

        for metric in metrics_iter:
            name = metric.get('canonical_name') or metric.get('metric_name') or metric.get('name_raw')
            if not name:
                continue
            slug = str(name).strip().lower().replace(' ', '_')
            numeric_value = metric.get('numeric_value')
            value = numeric_value if numeric_value is not None else metric.get('value_raw')
            metrics_json[slug] = {
                'value': value,
                'unit': metric.get('unit'),
                'period': metric.get('period'),
                'value_type': metric.get('value_type'),
                'value_raw': metric.get('value_raw'),
                'source_excerpt': metric.get('source_excerpt'),
                'description': metric.get('description'),
            }
            confidence_json[slug] = {
                'confidence': metric.get('confidence') or 1.0,
                'source': 'bem-v2',
            }
        return metrics_json, confidence_json

    @staticmethod
    def _to_list(value: Any) -> list:
        if not value:
            return []
        if isinstance(value, list):
            return value
        return [value]

    @staticmethod
    def _people_list(block: Any) -> list[dict[str, Any]]:
        if not isinstance(block, dict):
            return []
        people: list[dict[str, Any]] = []
        for key, record in block.items():
            if not isinstance(record, dict):
                continue
            entry = {'source_key': key}
            entry.update({k: v for k, v in record.items() if v is not None})
            people.append(entry)
        return people

    def _normalize_bem_output(self, raw: dict, response: dict) -> dict:
        extracted = self._extract_result(response)
        metrics_json, confidence_json = self._normalize_metrics(extracted.get('metrics'))

        period = infer_period(
            raw.get('subject'),
            extracted.get('reporting_period_raw') or raw.get('body_text') or '',
        )

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
            'highlights_json': self._to_list(extracted.get('highlights')),
            'asks_json': self._to_list(extracted.get('asks')),
            'risks_json': self._to_list(extracted.get('challenges')),
            'people_json': self._people_list(extracted.get('contactInformation')),
            'confidence_json': confidence_json,
            'source_path': raw.get('source_path'),
            'parser_version': 'bem-v2',
            'parser_provider': self.name,
        }

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def parse(self, raw: dict) -> ParsedUpdateResult:
        payload = self._build_payload(raw)
        response = self._call_bem(payload)
        update = self._normalize_bem_output(raw, response)
        return ParsedUpdateResult(update=update, provider_output=response)
