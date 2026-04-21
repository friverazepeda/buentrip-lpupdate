from __future__ import annotations

import unittest

from lpupdate.parse_updates import (
    clean_bullet_line,
    clean_bullet_list,
    normalize_update,
    parse_stringified_json_list,
    refine_summary_paragraph,
)


class TestNarrativeCleanup(unittest.TestCase):
    def test_strip_subject_prefix(self) -> None:
        self.assertEqual(clean_bullet_line("Subject: We closed a new round"), "We closed a new round")

    def test_strip_bracket_timestamp(self) -> None:
        self.assertTrue("revenue" in clean_bullet_line("[0.0] revenue grew YoY").lower())

    def test_refine_summary_drops_forwarded_noise(self) -> None:
        text = "Subject: Q4 Update\n\nForwarded message\n\nHere is the real summary paragraph with enough content."
        out = refine_summary_paragraph(text)
        self.assertNotIn("Forwarded message", out)
        self.assertNotIn("Subject:", out)

    def test_parse_stringified_list(self) -> None:
        self.assertEqual(
            parse_stringified_json_list('["a", "b"]'),
            ["a", "b"],
        )
        self.assertIsNone(parse_stringified_json_list("not json"))

    def test_normalize_subject_not_in_first_bullet(self) -> None:
        raw = {
            "gmail_message_id": "t1",
            "subject": "Co — Q4 2024",
            "body_text": "Highlights\n- Subject: This is a long enough bullet line for filters and should be cleaned.\n- Second point with enough characters here.\n\nRisks\n- Market risk described with sufficient detail here.\n",
            "received_at": "2024-12-01T00:00:00Z",
        }
        out = normalize_update(raw)
        for h in out.get("highlights_json") or []:
            self.assertNotRegex(h, r"(?i)^subject:")


class TestNormalizeEmptyMetricsGraceful(unittest.TestCase):
    def test_minimal_body_no_metrics(self) -> None:
        raw = {
            "gmail_message_id": "t2",
            "subject": "X — Q1 2025",
            "body_text": "Hello world.\n",
            "received_at": "2025-01-01T00:00:00Z",
        }
        out = normalize_update(raw)
        self.assertEqual(out.get("metrics_json"), {})


if __name__ == "__main__":
    unittest.main()
