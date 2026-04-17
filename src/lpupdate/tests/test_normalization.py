from datetime import datetime

from lpupdate.ingest import normalize_message
from lpupdate.fathom import normalize_fathom_meeting


def test_normalize_message_gmail_basic():
  raw = {
    "id": "abc123",
    "threadId": "thread-1",
    "snippet": "Snippet",
    "payload": {
      "headers": [
        {"name": "Subject", "value": "Quarterly Update"},
        {"name": "From", "value": "Founder <founder@example.com>"},
        {"name": "To", "value": "LP <lp@example.com>"},
        {"name": "Date", "value": "Fri, 01 Mar 2024 12:34:56 +0000"},
      ],
      "mimeType": "text/plain",
      "body": {"data": ""},
    },
  }
  label_ids = ["Label_1", "Label_2"]
  label_names = ["Investor/Quarterly", "Starred"]

  normalized = normalize_message(raw, label_ids, label_names)

  assert normalized["gmail_message_id"] == "abc123"
  assert normalized["gmail_thread_id"] == "thread-1"
  assert normalized["subject"] == "Quarterly Update"
  assert normalized["from_address"].startswith("Founder")
  assert normalized["to_addresses"] == ["LP <lp@example.com>"]
  # Original header is preserved.
  assert normalized["received_at"] == "Fri, 01 Mar 2024 12:34:56 +0000"
  # Normalized ISO timestamp is present and parseable.
  iso = normalized.get("received_at_iso")
  assert isinstance(iso, str) and iso
  dt = datetime.fromisoformat(iso)
  assert dt.year == 2024
  # Labels: ids and names both preserved.
  assert normalized["label_ids"] == label_ids
  assert normalized["label_names"] == label_names
  # Explicit source identity.
  assert normalized["source_type"] == "gmail_message"


def test_normalize_fathom_meeting_basic():
  meeting = {
    "recording_id": "f-1",
    "meeting_title": "Acme Corp Q1 Update",
    "recorded_by": {"email": "team@fathom.ai"},
    "calendar_invitees": [{"email": "lp@example.com"}],
    "created_at": "2025-01-01T12:34:56Z",
    "default_summary": {"markdown": "Summary text"},
    "transcript": [
      {"timestamp_seconds": 0.0, "speaker_name": "Founder", "text": "Intro"},
    ],
  }

  normalized = normalize_fathom_meeting(meeting)

  assert normalized["gmail_message_id"] == "fathom_f-1"
  assert normalized["gmail_thread_id"] == "fathom_f-1"
  assert normalized["subject"].startswith("Fathom Call:")
  assert normalized["from_address"] == "team@fathom.ai"
  assert normalized["to_addresses"] == ["lp@example.com"]
  # Original timestamp is preserved.
  assert normalized["received_at"] == "2025-01-01T12:34:56Z"
  # Normalized ISO timestamp is added.
  iso = normalized.get("received_at_iso")
  assert isinstance(iso, str) and iso
  dt = datetime.fromisoformat(iso)
  assert dt.year == 2025
  # Explicit source identity.
  assert normalized["source_type"] == "fathom_meeting"
