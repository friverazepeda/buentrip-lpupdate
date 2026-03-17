from __future__ import annotations

from .base import ParsedUpdateResult
from .bem import BemParseProvider
from .rules import RulesParseProvider


class HybridParseProvider:
    name = 'hybrid'

    def __init__(self, settings) -> None:
        self.settings = settings
        self.rules = RulesParseProvider()
        self.bem = BemParseProvider(settings)

    def parse(self, raw: dict) -> ParsedUpdateResult:
        rules_result = self.rules.parse(raw)
        try:
            bem_result = self.bem.parse(raw)
        except Exception as e:
            fallback = dict(rules_result.update)
            fallback['parser_provider'] = self.name
            fallback['parser_notes'] = [f'bem fallback to rules: {e}']
            return ParsedUpdateResult(update=fallback, provider_output={'fallback_reason': str(e)})

        merged = dict(rules_result.update)
        merged['parser_provider'] = self.name
        merged['parser_version'] = 'hybrid-v1'
        merged['parser_components'] = {
            'primary': 'bem',
            'fallback': 'rules',
        }

        for key in ['company_name', 'report_period_label', 'report_quarter', 'report_year', 'report_month', 'summary']:
            if bem_result.update.get(key):
                merged[key] = bem_result.update[key]

        for key in ['highlights_json', 'asks_json', 'risks_json']:
            if bem_result.update.get(key):
                merged[key] = bem_result.update[key]

        merged_metrics = dict(rules_result.update.get('metrics_json', {}))
        merged_metrics.update(bem_result.update.get('metrics_json', {}))
        merged['metrics_json'] = merged_metrics

        merged_confidence = dict(rules_result.update.get('confidence_json', {}))
        merged_confidence.update(bem_result.update.get('confidence_json', {}))
        merged['confidence_json'] = merged_confidence

        return ParsedUpdateResult(update=merged, provider_output={'bem': bem_result.provider_output})
