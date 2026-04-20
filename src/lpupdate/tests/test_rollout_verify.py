from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lpupdate.rollout_verify import (
    bootstrap_rollout_sample,
    verify_parsed_update_file,
    verify_rollout_artifacts,
    verify_sync_stage_summary,
)
from lpupdate.store import iter_data_record_json_files


class TestIterDataRecordJsonFiles(unittest.TestCase):
    def test_excludes_run_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "raw"
            d.mkdir()
            (d / "msg1.json").write_text("{}")
            (d / "run_summary.json").write_text("{}")
            names = [p.name for p in iter_data_record_json_files(d)]
            self.assertEqual(names, ["msg1.json"])


class TestVerifyParsedUpdateFile(unittest.TestCase):
    def test_valid_minimal_shape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.json"
            p.write_text(
                json.dumps(
                    {
                        "gmail_message_id": "m1",
                        "report_period_label": "Q4 2024",
                        "report_quarter": 4,
                        "report_year": 2024,
                        "received_at": "2024-01-01",
                        "summary": "s",
                        "metrics_json": {},
                        "highlights_json": [],
                        "asks_json": [],
                        "risks_json": [],
                    }
                )
            )
            self.assertEqual(verify_parsed_update_file(p), [])

    def test_rejects_bad_metrics_type(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.json"
            p.write_text(
                json.dumps(
                    {
                        "gmail_message_id": "m1",
                        "report_period_label": None,
                        "report_quarter": None,
                        "report_year": None,
                        "received_at": None,
                        "summary": None,
                        "metrics_json": [],
                        "highlights_json": [],
                        "asks_json": [],
                        "risks_json": [],
                    }
                )
            )
            errs = verify_parsed_update_file(p)
            self.assertTrue(any("metrics_json" in e for e in errs))


class TestVerifySyncStageSummary(unittest.TestCase):
    def test_skip_reasons_must_match_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            summary = {
                "stage": "sync_postgres",
                "skipped": 2,
                "skip_reasons": {"no_company_match": 1},
                "quarantined_count": 2,
                "quarantine_dir": str(root / "q"),
            }
            (root / "q").mkdir()
            (root / "q" / "a.json").write_text("{}")
            (root / "q" / "b.json").write_text("{}")
            errs = verify_sync_stage_summary(summary, root)
            self.assertTrue(any("skip_reasons" in e for e in errs))

    def test_passes_when_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            q = root / "q"
            q.mkdir()
            for name, code in (("a.json", "no_company_match"), ("b.json", "raw_source_missing")):
                (q / name).write_text(
                    json.dumps({"reason_code": code, "synced": False}),
                )
            summary = {
                "stage": "sync_postgres",
                "parsed": 2,
                "skipped": 2,
                "skip_reasons": {"no_company_match": 1, "raw_source_missing": 1},
                "quarantined_count": 2,
                "quarantine_dir": str(q),
            }
            self.assertEqual(verify_sync_stage_summary(summary, root), [])


class TestBootstrapRolloutSample(unittest.TestCase):
    def test_copies_into_data_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "rollout_samples" / "raw_gmail").mkdir(parents=True)
            (root / "rollout_samples" / "raw_fathom").mkdir(parents=True)
            (root / "rollout_samples" / "raw_gmail" / "g1.json").write_text('{"a": 1}')
            (root / "rollout_samples" / "raw_fathom" / "f1.json").write_text('{"b": 2}')
            out = bootstrap_rollout_sample(root, overwrite=True)
            self.assertEqual(len(out["copied"]), 2)
            self.assertEqual(out["skipped"], [])
            self.assertEqual((root / "data" / "raw_gmail" / "g1.json").read_text(), '{"a": 1}')


class TestVerifyRolloutArtifacts(unittest.TestCase):
    def test_parse_only_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pd = root / "data" / "parsed_updates"
            pd.mkdir(parents=True)
            (pd / "run_summary.json").write_text(
                json.dumps({"stage": "parse_raw", "parsed": 1, "skipped": 0, "failed": 0}),
            )
            (pd / "m1.json").write_text(
                json.dumps(
                    {
                        "gmail_message_id": "m1",
                        "report_period_label": None,
                        "report_quarter": None,
                        "report_year": None,
                        "received_at": None,
                        "summary": None,
                        "metrics_json": {},
                        "highlights_json": [],
                        "asks_json": [],
                        "risks_json": [],
                    }
                ),
            )
            errs = verify_rollout_artifacts(root, require_sync_summary=False)
            self.assertEqual(errs, [])
