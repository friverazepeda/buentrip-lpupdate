"""
Parser regression suite (roadmap A.1).

Loads JSON fixtures from tests/fixtures/parser_regression/*.json and asserts
stable outcomes from normalize_update() (rules-layer parsing, no BEM).
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from lpupdate.parse_updates import normalize_update

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "parser_regression"


class TestParserRegressionFixtures(unittest.TestCase):
    def test_all_fixtures(self) -> None:
        paths = sorted(FIXTURE_DIR.glob("*.json"))
        self.assertTrue(paths, f"no fixtures under {FIXTURE_DIR}")
        for path in paths:
            with self.subTest(fixture=path.name):
                bundle = json.loads(path.read_text())
                raw = bundle["raw"]
                exp = bundle["expected"]
                out = normalize_update(raw)
                metrics = out.get("metrics_json") or {}
                if "metrics_keys_contain" in exp:
                    for key in exp["metrics_keys_contain"]:
                        self.assertIn(key, metrics, f"missing metric key {key!r}")
                if "min_metric_count" in exp:
                    self.assertGreaterEqual(
                        len(metrics),
                        int(exp["min_metric_count"]),
                        f"expected at least {exp['min_metric_count']} metrics",
                    )
                if "report_year" in exp and exp["report_year"] is not None:
                    self.assertEqual(out.get("report_year"), exp["report_year"])
                if "company_name_contains" in exp:
                    name = out.get("company_name") or ""
                    self.assertIn(exp["company_name_contains"], name)


if __name__ == "__main__":
    unittest.main()
