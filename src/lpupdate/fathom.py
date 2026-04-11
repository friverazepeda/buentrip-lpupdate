import urllib.request
import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)

class FathomClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.fathom.ai/external/v1"

    def _headers(self):
        return {
            'X-Api-Key': self.api_key,
            'Accept': 'application/json',
        }

    def list_meetings(self, limit: int = 10, include_transcript: bool = True, include_summary: bool = True, created_after: str | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor = None
        while len(results) < limit:
            page_size = min(50, max(1, limit - len(results)))
            url = f"{self.base_url}/meetings?limit={page_size}"
            if include_transcript:
                url += "&include_transcript=true"
            if include_summary:
                url += "&include_summary=true"
            if created_after:
                url += f"&created_after={created_after}"
            if cursor:
                url += f"&cursor={cursor}"
            req = urllib.request.Request(url, headers=self._headers())
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
            except HTTPError as e:
                raise RuntimeError(f"Fathom API error {e.code}: {e.read().decode('utf-8', errors='replace')}")
            except URLError as e:
                raise RuntimeError(f"Fathom API connection failed: {e}")
            items = data.get('items', [])
            results.extend(items)
            cursor = data.get('next_cursor')
            if not cursor or not items:
                break
        return results

def normalize_fathom_meeting(meeting: dict) -> dict:
    meeting_id = str(meeting.get('recording_id', ''))
    title = meeting.get('meeting_title') or meeting.get('title') or ''
    # Combine summary and transcript into body_text so the parser can handle it
    summary = meeting.get('default_summary', {}).get('markdown', '') if meeting.get('default_summary') else ''
    transcript_raw = meeting.get('transcript') or []
    if isinstance(transcript_raw, list):
        transcript = '\n'.join(f"[{seg.get('timestamp_seconds', 0.0)}] {seg.get('speaker_name', 'Unknown')}: {seg.get('text', '')}" for seg in transcript_raw if isinstance(seg, dict))
    else:
        transcript = str(transcript_raw)
    
    body_text = "FATHOM MEETING RECORDING\n"
    if summary:
        body_text += f"\n--- SUMMARY ---\n{summary}\n"
    if transcript:
        body_text += f"\n--- TRANSCRIPT ---\n{transcript}\n"

    return {
        'gmail_message_id': f"fathom_{meeting_id}",
        'gmail_thread_id': f"fathom_{meeting_id}",
        'subject': f"Fathom Call: {title}",
        'from_address': meeting.get('recorded_by', {}).get('email', 'unknown@fathom.video'),
        'to_addresses': [inv.get('email') for inv in meeting.get('calendar_invitees', []) if inv.get('email')],
        'received_at': meeting.get('created_at'),
        'body_text': body_text,
        'attachments': [],
        'source_type': 'fathom_meeting'
    }
