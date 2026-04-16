from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any


def _decode_base64url(data: str | None) -> str:
    if not data:
        return ''
    raw = base64.urlsafe_b64decode(data + '=' * (-len(data) % 4))
    return raw.decode('utf-8', errors='replace')


def _header_map(payload: dict[str, Any]) -> dict[str, str]:
    headers = payload.get('headers', []) or []
    return {h.get('name', '').lower(): h.get('value', '') for h in headers if h.get('name')}


def extract_plain_text(payload: dict[str, Any]) -> str:
    mime_type = payload.get('mimeType', '')
    body = payload.get('body', {}) or {}
    data = body.get('data')
    if mime_type == 'text/plain' and data:
        return _decode_base64url(data)

    parts = payload.get('parts', []) or []
    texts: list[str] = []
    for part in parts:
        part_type = part.get('mimeType', '')
        part_body = part.get('body', {}) or {}
        part_data = part_body.get('data')
        if part_type == 'text/plain' and part_data:
            texts.append(_decode_base64url(part_data))
        elif part.get('parts'):
            nested = extract_plain_text(part)
            if nested:
                texts.append(nested)
    return '\n\n'.join(t for t in texts if t).strip()


def extract_html_text(payload: dict[str, Any]) -> str:
    mime_type = payload.get('mimeType', '')
    body = payload.get('body', {}) or {}
    data = body.get('data')
    if mime_type == 'text/html' and data:
        return _decode_base64url(data)

    parts = payload.get('parts', []) or []
    texts: list[str] = []
    for part in parts:
        part_type = part.get('mimeType', '')
        part_body = part.get('body', {}) or {}
        part_data = part_body.get('data')
        if part_type == 'text/html' and part_data:
            texts.append(_decode_base64url(part_data))
        elif part.get('parts'):
            nested = extract_html_text(part)
            if nested:
                texts.append(nested)
    return '\n\n'.join(t for t in texts if t).strip()


def collect_attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(part: dict[str, Any]):
        filename = part.get('filename')
        mime_type = part.get('mimeType', '')
        body = part.get('body', {}) or {}
        attachment_id = body.get('attachmentId')
        if filename and attachment_id:
            found.append({
                'filename': filename,
                'mime_type': mime_type,
                'attachment_id': attachment_id,
            })
        for child in part.get('parts', []) or []:
            walk(child)

    walk(payload)
    return found


def save_attachment(service, message_id: str, attachment: dict[str, Any], out_dir: str | Path) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    resp = service.users().messages().attachments().get(
        userId='me',
        messageId=message_id,
        id=attachment['attachment_id'],
    ).execute()
    data = resp.get('data')
    raw = base64.urlsafe_b64decode(data + '=' * (-len(data) % 4))
    safe_name = Path(attachment['filename']).name
    path = out_dir / safe_name
    path.write_bytes(raw)
    return {
        'filename': safe_name,
        'mime_type': attachment.get('mime_type'),
        'gmail_attachment_id': attachment.get('attachment_id'),
        'storage_path': str(path),
    }


def _normalize_timestamp(value: str | None) -> str | None:
    """
    Normalize a timestamp string into ISO 8601 (UTC) where possible.

    This leaves the original header value untouched in the main record
    (`received_at`) so downstream code can continue to rely on it.
    """
    if not value:
        return None
    value = value.strip()
    if not value:
        return None

    # First try RFC2822 / Gmail Date header formats.
    try:
        dt = parsedate_to_datetime(value)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        pass

    # Fallback to ISO-style parsing if the string already looks close.
    try:
        cleaned = value.replace('Z', '+00:00')
        dt = datetime.fromisoformat(cleaned)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def normalize_message(message: dict[str, Any], label_ids: list[str], label_names: list[str]) -> dict[str, Any]:
    payload = message.get('payload', {}) or {}
    headers = _header_map(payload)
    received_raw = headers.get('date')
    return {
        'gmail_message_id': message.get('id'),
        'gmail_thread_id': message.get('threadId'),
        # Preserve both the raw Gmail labelIds and the resolved label names.
        'label_ids': label_ids,
        'label_names': label_names,
        # Explicit source identity for downstream analysis.
        'source_type': 'gmail_message',
        'subject': headers.get('subject'),
        'from_address': headers.get('from'),
        'to_addresses': [headers.get('to')] if headers.get('to') else [],
        # Keep the original header value for compatibility.
        'received_at': received_raw,
        # Add a normalized ISO-8601 representation for consistent analysis.
        'received_at_iso': _normalize_timestamp(received_raw),
        'snippet': message.get('snippet'),
        'body_text': extract_plain_text(payload),
        'body_html': extract_html_text(payload),
        'attachments': collect_attachments(payload),
        'raw_payload': message,
    }
