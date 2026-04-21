"""Unit tests for LLM JSON → parsed update mapping (no OpenAI calls)."""

from __future__ import annotations

import unittest

from lpupdate.extraction.map_to_update import llm_extraction_to_parsed_update
from lpupdate.parsers.base import SourceBundle


class TestLlmMapToUpdate(unittest.TestCase):
    def test_maps_sections_and_metrics(self) -> None:
        raw = {
            "gmail_message_id": "m1",
            "gmail_thread_id": "t1",
            "subject": "Acme — Q4 2025",
            "body_text": "ignored for this test",
            "received_at": "2025-12-01T00:00:00Z",
        }
        bundle = SourceBundle(
            body_text="",
            attachment_text="",
            combined_text="",
            attachment_count=0,
            attachment_text_present=False,
        )
        llm = {
            "companyName": "Acme",
            "reportPeriod": "Q4 2025",
            "sourceType": "gmail",
            "summary": "Strong quarter with solid revenue growth across regions.",
            "highlights": ["First highlight with enough characters in the string."],
            "asks": ["Warm intro to enterprise buyer in segment."],
            "risks": ["Competitive pressure in core market segment here."],
            "keyMetrics": [
                {
                    "name": "ARR",
                    "value": 1_200_000,
                    "unit": "USD",
                    "period": "annual",
                    "currency": "USD",
                    "confidence": "high",
                }
            ],
            "extractionNotes": [],
        }
        out = llm_extraction_to_parsed_update(raw, bundle, llm)
        self.assertEqual(out["gmail_message_id"], "m1")
        self.assertEqual(out["summary"], llm["summary"])
        self.assertIn("arr", out["metrics_json"])
        self.assertEqual(out["metrics_json"]["arr"].get("value"), 1_200_000)
        self.assertEqual(out["confidence_json"]["arr"]["origin"], "llm_extraction")
        self.assertEqual(len(out["highlights_json"]), 1)
        self.assertEqual(out["parser_version"], "llm-v1")


if __name__ == "__main__":
    unittest.main()
