from __future__ import annotations

import json
from typing import Any, Iterable

from .base import ParsedUpdateResult
from .bem import BemParseProvider
from .rules import RulesParseProvider


class HybridParseProvider:
    name = 'hybrid'

    def __init__(self, settings) -> None:
        self.settings = settings
        self.rules = RulesParseProvider()
        self.bem = BemParseProvider(settings)
        self.section_override_threshold = getattr(settings, 'hybrid_section_override_threshold', 2)

    @staticmethod
    def _coerce_list(value: Any) -> list:
        if not value:
            return []
        if isinstance(value, list):
            return value
        return [value]

    @staticmethod
    def _dedupe_entries(entries: Iterable[Any]) -> list:
        seen: set[str] = set()
        deduped: list[Any] = []
        for entry in entries:
            if entry is None:
                continue
            if isinstance(entry, (str, int, float)):
                key = str(entry).strip()
            else:
                try:
                    key = json.dumps(entry, sort_keys=True, default=str)
                except TypeError:
                    key = str(entry)
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        return deduped

    def _merge_section_lists(self, bem_entries: Any, rules_entries: Any) -> list:
        bem_list = self._coerce_list(bem_entries)
        rules_list = self._coerce_list(rules_entries)

        if len(bem_list) >= self.section_override_threshold:
            return self._dedupe_entries(bem_list)
        if bem_list:
            return self._dedupe_entries(bem_list + rules_list)
        return self._dedupe_entries(rules_list)

    def parse(self, raw: dict) -> ParsedUpdateResult:
        rules_result = self.rules.parse(raw)
        try:
            bem_result = self.bem.parse(raw)
        except Exception as e:
            fallback = dict(rules_result.update)
            fallback['parser_provider'] = self.name
            existing_notes = fallback.get('parser_notes')
            if isinstance(existing_notes, list):
                notes = list(existing_notes)
            elif existing_notes:
                notes = [str(existing_notes)]
            else:
                notes = []
            notes.append(f'bem fallback to rules: {e}')
            fallback['parser_notes'] = notes
            # Observability: full rules output after BEM failure (no merge).
            pc = dict(fallback.get('parser_components') or {})
            pc.update({
                'primary': 'bem',
                'fallback': 'rules',
                'hybrid_winner': 'rules_only',
                'fallback_occurred': True,
                'fallback_reason': str(e),
            })
            fallback['parser_components'] = pc
            return ParsedUpdateResult(
                update=fallback,
                provider_output={
                    'fallback_reason': str(e),
                    'hybrid_trace': {
                        'hybrid_winner': 'rules_only',
                        'fallback_occurred': True,
                        'fallback_reason': str(e),
                    },
                },
            )

        merged = dict(rules_result.update)
        merged['parser_provider'] = self.name
        merged['parser_version'] = 'hybrid-v1'
        # Which provider supplied key scalar fields (for debugging; same keys as before).
        field_sources: dict[str, str] = {}
        for key in ['company_name', 'report_period_label', 'report_quarter', 'report_year', 'report_month', 'summary']:
            bem_val = bem_result.update.get(key)
            rules_val = rules_result.update.get(key)
            if bem_val:
                field_sources[key] = 'bem'
            elif rules_val:
                field_sources[key] = 'rules'
            else:
                field_sources[key] = 'none'

        merged['parser_components'] = {
            'primary': 'bem',
            'fallback': 'rules',
            'hybrid_winner': 'merged',
            'fallback_occurred': False,
            'fallback_reason': None,
            'field_sources': field_sources,
        }

        for key in ['company_name', 'report_period_label', 'report_quarter', 'report_year', 'report_month', 'summary']:
            if bem_result.update.get(key):
                merged[key] = bem_result.update[key]

        for key in ['highlights_json', 'asks_json', 'risks_json']:
            merged[key] = self._merge_section_lists(
                bem_result.update.get(key),
                rules_result.update.get(key),
            )

        merged_metrics = dict(rules_result.update.get('metrics_json', {}))
        merged_metrics.update(bem_result.update.get('metrics_json', {}))
        merged['metrics_json'] = merged_metrics

        merged_confidence = dict(rules_result.update.get('confidence_json', {}))
        merged_confidence.update(bem_result.update.get('confidence_json', {}))
        merged['confidence_json'] = merged_confidence

        return ParsedUpdateResult(
            update=merged,
            provider_output={
                'bem': bem_result.provider_output,
                'hybrid_trace': {
                    'hybrid_winner': 'merged',
                    'fallback_occurred': False,
                    'fallback_reason': None,
                    'field_sources': field_sources,
                },
            },
        )
