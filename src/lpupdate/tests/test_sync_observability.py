from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

# Stub Google modules used by lpupdate.cli import path in minimal test envs.
if "google" not in sys.modules:
    sys.modules["google"] = types.ModuleType("google")
if "google.oauth2" not in sys.modules:
    sys.modules["google.oauth2"] = types.ModuleType("google.oauth2")
if "google.oauth2.credentials" not in sys.modules:
    mod = types.ModuleType("google.oauth2.credentials")

    class _Credentials:  # pragma: no cover - stub only
        pass

    mod.Credentials = _Credentials
    sys.modules["google.oauth2.credentials"] = mod
if "google.oauth2.service_account" not in sys.modules:
    mod = types.ModuleType("google.oauth2.service_account")

    class _SACreds:  # pragma: no cover - stub only
        @classmethod
        def from_service_account_file(cls, *_args, **_kwargs):
            return cls()

        def with_subject(self, *_args, **_kwargs):
            return self

    mod.Credentials = _SACreds
    sys.modules["google.oauth2.service_account"] = mod
if "google.auth" not in sys.modules:
    sys.modules["google.auth"] = types.ModuleType("google.auth")
if "google.auth.transport" not in sys.modules:
    sys.modules["google.auth.transport"] = types.ModuleType("google.auth.transport")
if "google.auth.transport.requests" not in sys.modules:
    mod = types.ModuleType("google.auth.transport.requests")

    class _Request:  # pragma: no cover - stub only
        pass

    mod.Request = _Request
    sys.modules["google.auth.transport.requests"] = mod
if "google_auth_oauthlib" not in sys.modules:
    sys.modules["google_auth_oauthlib"] = types.ModuleType("google_auth_oauthlib")
if "google_auth_oauthlib.flow" not in sys.modules:
    mod = types.ModuleType("google_auth_oauthlib.flow")

    class _Flow:  # pragma: no cover - stub only
        pass

    mod.InstalledAppFlow = _Flow
    sys.modules["google_auth_oauthlib.flow"] = mod
if "googleapiclient" not in sys.modules:
    sys.modules["googleapiclient"] = types.ModuleType("googleapiclient")
if "googleapiclient.discovery" not in sys.modules:
    mod = types.ModuleType("googleapiclient.discovery")

    def _build(*_args, **_kwargs):  # pragma: no cover - stub only
        raise RuntimeError("stubbed googleapiclient.build called unexpectedly")

    mod.build = _build
    sys.modules["googleapiclient.discovery"] = mod
if "psycopg2" not in sys.modules:
    mod = types.ModuleType("psycopg2")

    def _connect(*_args, **_kwargs):  # pragma: no cover - stub only
        raise RuntimeError("stubbed psycopg2.connect called unexpectedly")

    mod.connect = _connect
    sys.modules["psycopg2"] = mod
if "psycopg2.extras" not in sys.modules:
    mod = types.ModuleType("psycopg2.extras")

    class _RealDictCursor:  # pragma: no cover - stub only
        pass

    mod.RealDictCursor = _RealDictCursor
    sys.modules["psycopg2.extras"] = mod

import lpupdate.cli as cli


class _FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, *_args, **_kwargs):
        return None


class _FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor()

    def commit(self):
        return None


class TestSyncObservability(unittest.TestCase):
    def _read_json(self, path: Path) -> dict:
        return json.loads(path.read_text())

    def test_sync_writes_quarantine_for_no_company_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parsed_dir = root / "data" / "parsed_updates"
            raw_dir = root / "data" / "raw_gmail"
            fathom_dir = root / "data" / "raw_fathom"
            parsed_dir.mkdir(parents=True, exist_ok=True)
            raw_dir.mkdir(parents=True, exist_ok=True)
            fathom_dir.mkdir(parents=True, exist_ok=True)

            parsed = {
                "gmail_message_id": "m1",
                "company_name": None,
                "summary": "",
                "metrics_json": {},
                "highlights_json": [],
                "asks_json": [],
                "risks_json": [],
            }
            raw = {"gmail_message_id": "m1", "subject": "Subj"}
            (parsed_dir / "m1.json").write_text(json.dumps(parsed))
            (raw_dir / "m1.json").write_text(json.dumps(raw))

            args = SimpleNamespace(limit=100, source="all")
            fake_settings = SimpleNamespace(database_url="postgres://fake")

            def ensure_data_dir_side_effect(p):
                path = root / p
                path.mkdir(parents=True, exist_ok=True)
                return path

            with patch("lpupdate.cli.Settings.from_env", return_value=fake_settings), patch(
                "lpupdate.cli.ensure_data_dir", side_effect=ensure_data_dir_side_effect
            ), patch("lpupdate.cli.connect", return_value=_FakeConnection()), patch(
                "lpupdate.cli.upsert_company", return_value=None
            ), patch(
                "lpupdate.cli.upsert_email_message", return_value=111
            ), patch(
                "lpupdate.cli.upsert_quarterly_update", return_value=None
            ):
                rc = cli.cmd_sync_postgres(args)
                self.assertEqual(rc, 0)

            quarantine_file = root / "data" / "quarantine_unsynced" / "m1.json"
            self.assertTrue(quarantine_file.exists())
            payload = self._read_json(quarantine_file)
            self.assertEqual(payload["reason_code"], "no_company_match")
            self.assertFalse(payload["synced"])
            self.assertEqual(payload["gmail_message_id"], "m1")

            summary_file = root / "data" / "parsed_updates" / "run_summary.json"
            self.assertTrue(summary_file.exists())
            summary = self._read_json(summary_file)
            self.assertEqual(summary.get("quarantined_count"), 1)
            self.assertIn("quarantine_unsynced", summary.get("quarantine_dir", ""))
            self.assertEqual(summary.get("skip_reasons", {}).get("no_company_match"), 1)

    def test_sync_writes_quarantine_when_raw_source_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parsed_dir = root / "data" / "parsed_updates"
            parsed_dir.mkdir(parents=True, exist_ok=True)

            parsed = {"gmail_message_id": "missing_raw", "company_name": "Acme"}
            (parsed_dir / "missing_raw.json").write_text(json.dumps(parsed))

            args = SimpleNamespace(limit=100, source="all")
            fake_settings = SimpleNamespace(database_url="postgres://fake")

            def ensure_data_dir_side_effect(p):
                path = root / p
                path.mkdir(parents=True, exist_ok=True)
                return path

            with patch("lpupdate.cli.Settings.from_env", return_value=fake_settings), patch(
                "lpupdate.cli.ensure_data_dir", side_effect=ensure_data_dir_side_effect
            ), patch("lpupdate.cli.connect", return_value=_FakeConnection()):
                rc = cli.cmd_sync_postgres(args)
                self.assertEqual(rc, 0)

            quarantine_file = root / "data" / "quarantine_unsynced" / "missing_raw.json"
            self.assertTrue(quarantine_file.exists())
            payload = self._read_json(quarantine_file)
            self.assertEqual(payload["reason_code"], "raw_source_missing")

            summary_file = root / "data" / "parsed_updates" / "run_summary.json"
            summary = self._read_json(summary_file)
            self.assertEqual(summary.get("skip_reasons", {}).get("raw_source_missing"), 1)


if __name__ == "__main__":
    unittest.main()
