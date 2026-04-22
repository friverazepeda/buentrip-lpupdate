"""Tests for rules-parser resilience and hybrid observability (fixtures).

Run from the repository root (the directory that contains the ``src/`` folder)::

    export PYTHONPATH="$(pwd)/src"
    python3 -m unittest discover -s src/lpupdate/tests -p 'test_parse_resilience.py' -v

Or, with the dotted module path (same ``PYTHONPATH`` and repo root)::

    export PYTHONPATH="$(pwd)/src"
    python3 -m unittest lpupdate.tests.test_parse_resilience -v
"""

from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Importing lpupdate.parsers loads pdf_extract, which requires pypdf. Stub when absent
# so these tests run in minimal environments.
if "pypdf" not in sys.modules:
    _stub = types.ModuleType("pypdf")

    class _PdfReader:  # pragma: no cover - stub only
        pass

    _stub.PdfReader = _PdfReader
    sys.modules["pypdf"] = _stub

from lpupdate.parse_updates import normalize_update
from lpupdate.parsers.base import ParsedUpdateResult
from lpupdate.parsers.hybrid import HybridParseProvider

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Stable set of top-level keys expected on every parsed update (contract).
PARSED_UPDATE_KEYS = frozenset({
    "gmail_message_id",
    "gmail_thread_id",
    "company_name",
    "subject",
    "from_address",
    "to_addresses",
    "received_at",
    "report_period_label",
    "report_quarter",
    "report_year",
    "report_month",
    "summary",
    "metrics_json",
    "highlights_json",
    "asks_json",
    "risks_json",
    "people_json",
    "confidence_json",
    "source_path",
    "parser_version",
    "source_occurred_at",
    "source_type",
})


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestParseResilience(unittest.TestCase):
    def test_normalize_update_gmail_fixture_shape_and_no_crash(self):
        raw = _load_fixture("raw_gmail_sample.json")
        out = normalize_update(raw)
        self.assertEqual(set(out.keys()), PARSED_UPDATE_KEYS)
        self.assertEqual(out["gmail_message_id"], "fixture_gmail_1")
        self.assertIsInstance(out["metrics_json"], dict)
        self.assertIsInstance(out["highlights_json"], list)
        self.assertIsInstance(out["asks_json"], list)
        self.assertIsInstance(out["risks_json"], list)

    def test_normalize_update_fathom_fixture_shape_and_no_crash(self):
        raw = _load_fixture("raw_fathom_sample.json")
        out = normalize_update(raw)
        self.assertEqual(set(out.keys()), PARSED_UPDATE_KEYS)
        self.assertTrue(
            "fathom" in (out["gmail_message_id"] or "").lower()
            or out["gmail_message_id"] == "fathom_fixture_rec_1",
        )

    def test_normalize_update_tolerates_non_string_subject_and_body(self):
        raw = {
            "gmail_message_id": "edge_1",
            "gmail_thread_id": "t1",
            "subject": None,
            "body_text": 12345,
            "attachment_text": None,
            "from_address": "a@b.co",
            "to_addresses": [],
            "received_at": None,
        }
        out = normalize_update(raw)
        self.assertEqual(set(out.keys()), PARSED_UPDATE_KEYS)
        self.assertEqual(out["gmail_message_id"], "edge_1")

    def test_hybrid_fallback_sets_parser_components(self):
        settings = MagicMock()
        settings.hybrid_section_override_threshold = 2
        mock_bem = MagicMock()
        mock_bem.parse.side_effect = RuntimeError("bem unavailable")
        with patch("lpupdate.parsers.hybrid.BemParseProvider", return_value=mock_bem):
            hp = HybridParseProvider(settings)
        raw = {
            "gmail_message_id": "hybrid_fb_1",
            "gmail_thread_id": "t",
            "subject": "Co — Q1 2024 Investor Update",
            "body_text": "Highlights\n- A sufficiently long bullet point for the parser filters.\n",
            "from_address": "x@y.z",
            "to_addresses": [],
            "received_at": "2024-01-01",
        }
        result = hp.parse(raw)
        pc = result.update.get("parser_components") or {}
        self.assertTrue(pc.get("fallback_occurred"))
        self.assertEqual(pc.get("hybrid_winner"), "rules_only")
        self.assertEqual(pc.get("fallback_reason"), "bem unavailable")
        self.assertEqual(result.update["parser_provider"], "hybrid")
        trace = (result.provider_output or {}).get("hybrid_trace") or {}
        self.assertTrue(trace.get("fallback_occurred"))

    def test_hybrid_merge_sets_field_sources_and_trace(self):
        settings = MagicMock()
        settings.hybrid_section_override_threshold = 2

        rules_update = normalize_update({
            "gmail_message_id": "hybrid_ok_1",
            "gmail_thread_id": "t",
            "subject": "Delta LLC — Q2 2024 Investor Update",
            "body_text": (
                "Highlights\n"
                "- First bullet point with enough characters to pass filters here.\n"
            ),
            "from_address": "a@b.c",
            "to_addresses": [],
            "received_at": "2024-04-01",
        })
        bem_update = dict(rules_update)
        bem_update["company_name"] = "Bem Override Co"
        bem_update["summary"] = "BEM summary text"
        bem_update["metrics_json"] = {"custom_metric": {"value": 1}}
        bem_update["parser_provider"] = "bem"
        bem_update["parser_version"] = "bem-v2"

        mock_bem = MagicMock()
        mock_bem.parse.return_value = ParsedUpdateResult(update=bem_update, provider_output={"ok": True})
        with patch("lpupdate.parsers.hybrid.BemParseProvider", return_value=mock_bem):
            hp = HybridParseProvider(settings)

        raw = {
            "gmail_message_id": "hybrid_ok_1",
            "gmail_thread_id": "t",
            "subject": "Delta LLC — Q2 2024 Investor Update",
            "body_text": (
                "Highlights\n"
                "- First bullet point with enough characters to pass filters here.\n"
                "How you can help\n"
                "- Introductions to enterprise buyers.\n"
            ),
            "from_address": "a@b.c",
            "to_addresses": [],
            "received_at": "2024-04-01",
        }
        result = hp.parse(raw)
        pc = result.update.get("parser_components") or {}
        self.assertFalse(pc.get("fallback_occurred"))
        self.assertEqual(pc.get("hybrid_winner"), "merged")
        self.assertEqual(pc.get("field_sources", {}).get("company_name"), "bem")
        trace = (result.provider_output or {}).get("hybrid_trace") or {}
        self.assertEqual(trace.get("hybrid_winner"), "merged")
        self.assertFalse(trace.get("fallback_occurred"))


if __name__ == "__main__":
    unittest.main()
