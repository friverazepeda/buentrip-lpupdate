from __future__ import annotations

from ..parse_updates import normalize_update
from .base import ParsedUpdateResult


class RulesParseProvider:
    name = 'rules'

    def parse(self, raw: dict) -> ParsedUpdateResult:
        update = normalize_update(raw)
        update['parser_provider'] = self.name
        return ParsedUpdateResult(update=update, provider_output=None)
