from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Settings, load_dotenv
from .gmail import (
    GmailClientConfig,
    build_gmail_client,
    build_manual_auth_url,
    exchange_code_for_token,
    get_credentials,
)
from .db import apply_schema, connect, get_company_metrics, get_company_updates, get_update, list_companies, list_updates, upsert_company, upsert_email_message, upsert_quarterly_update
from .ingest import normalize_message, save_attachment
from .parse_updates import load_raw_message, normalize_update
from .pdf_extract import extract_pdf_text
from .reporting import generate_report_site
from .schema import SCHEMA_SQL
from .store import ensure_data_dir, write_json


def cmd_doctor(_: argparse.Namespace) -> int:
    settings = Settings.from_env()
    payload = {
        "google_oauth_client_secret_file": settings.google_oauth_client_secret_file,
        "google_oauth_token_file": settings.google_oauth_token_file,
        "gmail_query": settings.gmail_query,
        "database_url_present": bool(settings.database_url),
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_gmail_auth(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if not settings.google_oauth_client_secret_file:
        raise FileNotFoundError("GOOGLE_OAUTH_CLIENT_SECRET_FILE is not set")
    if not settings.google_oauth_token_file:
        raise FileNotFoundError("GOOGLE_OAUTH_TOKEN_FILE is not set")

    if args.code_or_url:
        creds = exchange_code_for_token(
            settings.google_oauth_client_secret_file,
            settings.google_oauth_token_file,
            args.code_or_url,
        )
        print(json.dumps({
            "token_file": settings.google_oauth_token_file,
            "token_saved": True,
            "client_id": getattr(creds, 'client_id', None),
            "scopes": list(getattr(creds, 'scopes', []) or []),
        }, indent=2))
        return 0

    _flow, auth_url, _state = build_manual_auth_url(
        settings.google_oauth_client_secret_file,
        settings.google_oauth_token_file,
    )
    print(json.dumps({
        "auth_url": auth_url,
        "instructions": [
            "Open auth_url in your browser",
            "Approve access as manuel@buentrip.vc",
            "Copy the full redirected URL from the browser address bar",
            "Run: lpupdate gmail-auth --code-or-url '<PASTE_FULL_REDIRECT_URL>'",
            "Do not regenerate the auth URL before exchanging the redirect URL, or the PKCE verifier will change",
        ],
        "token_file": settings.google_oauth_token_file,
        "pkce_state_file": settings.google_oauth_token_file + '.pkce.json',
    }, indent=2))
    return 0


def cmd_gmail_check(_: argparse.Namespace) -> int:
    settings = Settings.from_env()
    cfg = GmailClientConfig(
        client_secret_file=settings.google_oauth_client_secret_file,
        token_file=settings.google_oauth_token_file,
    )
    service = build_gmail_client(cfg)
    profile = service.users().getProfile(userId="me").execute()
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    matched = [label for label in labels if label.get("name") == "Investor/Quarterly"]
    print(json.dumps({
        "email_address": profile.get("emailAddress"),
        "messages_total": profile.get("messagesTotal"),
        "threads_total": profile.get("threadsTotal"),
        "label_found": bool(matched),
        "matches": matched,
    }, indent=2))
    return 0


def cmd_gmail_fetch(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    cfg = GmailClientConfig(
        client_secret_file=settings.google_oauth_client_secret_file,
        token_file=settings.google_oauth_token_file,
    )
    service = build_gmail_client(cfg)
    response = service.users().messages().list(
        userId="me",
        q=settings.gmail_query,
        maxResults=args.limit,
    ).execute()
    messages = response.get("messages", []) or []

    data_dir = ensure_data_dir("data/raw_gmail")
    attachment_dir = ensure_data_dir("data/attachments")
    fetched: list[dict] = []
    for item in messages:
        full = service.users().messages().get(
            userId="me",
            id=item["id"],
            format="full",
        ).execute()
        labels = full.get("labelIds", []) or []
        normalized = normalize_message(full, labels)
        saved_attachments = []
        for attachment in normalized.get("attachments", []):
            saved = save_attachment(service, item['id'], attachment, attachment_dir / item['id'])
            saved_attachments.append(saved)
        normalized['attachments'] = saved_attachments
        write_json(data_dir / f"{item['id']}.json", normalized)
        fetched.append({
            "gmail_message_id": normalized["gmail_message_id"],
            "subject": normalized["subject"],
            "from_address": normalized["from_address"],
            "received_at": normalized["received_at"],
            "attachment_count": len(saved_attachments),
            "path": str(data_dir / f"{item['id']}.json"),
        })

    print(json.dumps({
        "query": settings.gmail_query,
        "count": len(fetched),
        "messages": fetched,
    }, indent=2))
    return 0


def cmd_parse_raw(args: argparse.Namespace) -> int:
    raw_dir = ensure_data_dir("data/raw_gmail")
    out_dir = ensure_data_dir("data/parsed_updates")
    raw_files = sorted(raw_dir.glob("*.json"))[: args.limit]
    parsed: list[dict] = []
    for path in raw_files:
        raw = load_raw_message(path)
        raw['source_path'] = str(path)
        attachment_texts = []
        for attachment in raw.get('attachments', []) or []:
            storage_path = attachment.get('storage_path')
            mime_type = (attachment.get('mime_type') or '').lower()
            if not storage_path:
                continue
            if mime_type == 'application/pdf' or str(storage_path).lower().endswith('.pdf'):
                try:
                    text = extract_pdf_text(storage_path)
                except Exception:
                    text = ''
                if text:
                    attachment_texts.append(text)
        raw['attachment_text'] = '\n\n'.join(attachment_texts)
        update = normalize_update(raw)
        update['attachment_count'] = len(raw.get('attachments', []) or [])
        update['attachment_text_present'] = bool(raw.get('attachment_text'))
        write_json(out_dir / path.name, update)
        parsed.append({
            'gmail_message_id': update['gmail_message_id'],
            'company_name': update['company_name'],
            'report_period_label': update['report_period_label'],
            'path': str(out_dir / path.name),
        })
    print(json.dumps({'count': len(parsed), 'updates': parsed}, indent=2))
    return 0


def cmd_db_apply(_: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if not settings.database_url:
        raise ValueError('LPUPDATE_DATABASE_URL is not set')
    apply_schema(settings.database_url)
    print(json.dumps({'schema_applied': True}, indent=2))
    return 0


def cmd_sync_postgres(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if not settings.database_url:
        raise ValueError('LPUPDATE_DATABASE_URL is not set')

    raw_dir = ensure_data_dir('data/raw_gmail')
    parsed_dir = ensure_data_dir('data/parsed_updates')
    parsed_files = sorted(parsed_dir.glob('*.json'))[: args.limit]
    synced: list[dict] = []

    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            for parsed_path in parsed_files:
                parsed = load_raw_message(parsed_path)
                raw_path = raw_dir / parsed_path.name
                raw = load_raw_message(raw_path)
                company_id = None
                if parsed.get('company_name'):
                    company_id = upsert_company(cur, parsed['company_name'])
                email_message_id = upsert_email_message(cur, raw)
                update_id = upsert_quarterly_update(cur, email_message_id, company_id, parsed)
                synced.append({
                    'gmail_message_id': parsed.get('gmail_message_id'),
                    'company_name': parsed.get('company_name'),
                    'email_message_id': email_message_id,
                    'quarterly_update_id': update_id,
                })
        conn.commit()

    print(json.dumps({'count': len(synced), 'synced': synced}, indent=2))
    return 0


def cmd_list_updates(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if not settings.database_url:
        raise ValueError('LPUPDATE_DATABASE_URL is not set')
    rows = list_updates(settings.database_url, limit=args.limit)
    print(json.dumps(rows, indent=2, default=str))
    return 0


def cmd_show_update(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if not settings.database_url:
        raise ValueError('LPUPDATE_DATABASE_URL is not set')
    row = get_update(settings.database_url, args.update_id)
    if not row:
        raise SystemExit(f'No update found for id={args.update_id}')
    print(json.dumps(row, indent=2, default=str))
    return 0


def cmd_list_companies(_: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if not settings.database_url:
        raise ValueError('LPUPDATE_DATABASE_URL is not set')
    rows = list_companies(settings.database_url)
    print(json.dumps(rows, indent=2, default=str))
    return 0


def cmd_show_company(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if not settings.database_url:
        raise ValueError('LPUPDATE_DATABASE_URL is not set')
    rows = get_company_updates(settings.database_url, args.company_name)
    if not rows:
        raise SystemExit(f'No updates found for company={args.company_name}')
    print(json.dumps(rows, indent=2, default=str))
    return 0


def cmd_company_metrics(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if not settings.database_url:
        raise ValueError('LPUPDATE_DATABASE_URL is not set')
    rows = get_company_metrics(settings.database_url, args.company_name)
    if not rows:
        raise SystemExit(f'No metrics found for company={args.company_name}')
    print(json.dumps(rows, indent=2, default=str))
    return 0


def cmd_show_raw_email(args: argparse.Namespace) -> int:
    raw_dir = ensure_data_dir('data/raw_gmail')
    path = raw_dir / f'{args.gmail_message_id}.json'
    if not path.exists():
        raise SystemExit(f'Raw email not found: {path}')
    raw = load_raw_message(path)
    print(json.dumps(raw, indent=2, default=str))
    return 0


def cmd_show_attachment_text(args: argparse.Namespace) -> int:
    raw_dir = ensure_data_dir('data/raw_gmail')
    path = raw_dir / f'{args.gmail_message_id}.json'
    if not path.exists():
        raise SystemExit(f'Raw email not found: {path}')
    raw = load_raw_message(path)
    attachments = raw.get('attachments', []) or []
    out = []
    for attachment in attachments:
        storage_path = attachment.get('storage_path')
        mime_type = (attachment.get('mime_type') or '').lower()
        text = None
        if storage_path and (mime_type == 'application/pdf' or str(storage_path).lower().endswith('.pdf')):
            try:
                text = extract_pdf_text(storage_path)
            except Exception as e:
                text = f'[pdf extract failed: {e}]'
        out.append({
            'filename': attachment.get('filename'),
            'mime_type': mime_type,
            'storage_path': storage_path,
            'text_excerpt': text[:args.max_chars] if text else None,
        })
    print(json.dumps(out, indent=2, default=str))
    return 0


def cmd_generate_report(_: argparse.Namespace) -> int:
    parsed_dir = ensure_data_dir('data/parsed_updates')
    out_dir = ensure_data_dir('reports')
    result = generate_report_site(parsed_dir, out_dir)
    print(json.dumps(result, indent=2))
    return 0


def cmd_print_schema(_: argparse.Namespace) -> int:
    print(SCHEMA_SQL.strip())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lpupdate")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="show current config wiring")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("gmail-auth", help="manual Gmail OAuth flow and token exchange")
    p.add_argument("--code-or-url", help="authorization code or full redirect URL from Google")
    p.set_defaults(func=cmd_gmail_auth)

    p = sub.add_parser("gmail-check", help="verify Gmail API access and label visibility")
    p.set_defaults(func=cmd_gmail_check)

    p = sub.add_parser("gmail-fetch", help="fetch raw Gmail messages for the configured query")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_gmail_fetch)

    p = sub.add_parser("parse-raw", help="parse fetched raw Gmail messages into normalized update JSON")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_parse_raw)

    p = sub.add_parser("db-apply", help="apply Postgres schema")
    p.set_defaults(func=cmd_db_apply)

    p = sub.add_parser("sync-postgres", help="sync parsed updates into Postgres")
    p.add_argument("--limit", type=int, default=100)
    p.set_defaults(func=cmd_sync_postgres)

    p = sub.add_parser("list-updates", help="list synced updates from Postgres")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_list_updates)

    p = sub.add_parser("show-update", help="show one synced update from Postgres")
    p.add_argument("update_id", type=int)
    p.set_defaults(func=cmd_show_update)

    p = sub.add_parser("list-companies", help="list companies present in synced updates")
    p.set_defaults(func=cmd_list_companies)

    p = sub.add_parser("show-company", help="show all synced updates for a company")
    p.add_argument("company_name")
    p.set_defaults(func=cmd_show_company)

    p = sub.add_parser("company-metrics", help="show only metrics for a company across updates")
    p.add_argument("company_name")
    p.set_defaults(func=cmd_company_metrics)

    p = sub.add_parser("show-raw-email", help="show one raw fetched email JSON by Gmail message id")
    p.add_argument("gmail_message_id")
    p.set_defaults(func=cmd_show_raw_email)

    p = sub.add_parser("show-attachment-text", help="extract and show text from PDF attachments for a message")
    p.add_argument("gmail_message_id")
    p.add_argument("--max-chars", type=int, default=4000)
    p.set_defaults(func=cmd_show_attachment_text)

    p = sub.add_parser("generate-report", help="generate static one-page-per-startup report site")
    p.set_defaults(func=cmd_generate_report)

    p = sub.add_parser("print-schema", help="print proposed Postgres schema")
    p.set_defaults(func=cmd_print_schema)

    return parser


def main() -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
