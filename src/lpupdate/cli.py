from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

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
from .parse_updates import load_raw_message
from .parsers import build_source_bundle, get_parse_provider
from .reporting import generate_report_site
from .schema import SCHEMA_SQL
from .store import ensure_data_dir, write_json


def _new_stage_summary(stage: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "fetched": 0,
        "parsed": 0,
        "skipped": 0,
        "failed": 0,
        "skip_reasons": {},
        "failed_reasons": {},
    }


def _increment_reason(summary: dict[str, Any], bucket: str, reason: str) -> None:
    counts = summary[bucket]
    counts[reason] = counts.get(reason, 0) + 1


def _write_stage_summary(stage_dir: Path, summary: dict[str, Any], extra: dict[str, Any] | None = None) -> str:
    payload = dict(summary)
    payload["generated_at_epoch_ms"] = int(time.time() * 1000)
    if extra:
        payload.update(extra)
    path = stage_dir / "run_summary.json"
    write_json(path, payload)
    return str(path)


def cmd_doctor(_: argparse.Namespace) -> int:
    settings = Settings.from_env()
    payload = {
        "google_oauth_client_secret_file": settings.google_oauth_client_secret_file,
        "google_oauth_token_file": settings.google_oauth_token_file,
        "gmail_query": settings.gmail_query,
        "database_url_present": bool(settings.database_url),
        "parse_provider": settings.parse_provider,
        "bem_api_url": settings.bem_api_url,
        "bem_api_key_present": bool(settings.bem_api_key),
        "bem_timeout_seconds": settings.bem_timeout_seconds,
        "bem_function_name": settings.bem_function_name,
        "bem_workflow_name": settings.bem_workflow_name,
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
        service_account_file=settings.google_service_account_file,
        service_account_subject=settings.google_service_account_subject,
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


def cmd_fathom_fetch(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if not settings.fathom_api_key:
        raise ValueError("FATHOM_API_KEY is not set")
    from .fathom import FathomClient, normalize_fathom_meeting
    from .store import ensure_data_dir, write_json
    import json
    client = FathomClient(settings.fathom_api_key)
    summary = _new_stage_summary("fathom_fetch")
    meetings = client.list_meetings(limit=args.limit, include_transcript=True, include_summary=True, created_after=args.created_after)
    if args.title_match:
        meetings = [m for m in meetings if args.title_match.lower() in (m.get('title') or '').lower()]
    if args.company_match:
        from .db import list_companies
        rows = list_companies(settings.database_url)
        known_companies = [r['canonical_name'].lower() for r in rows] if rows else []
        matched = []
        for m in meetings:
            title = (m.get('title') or '').lower()
            if any(company in title for company in known_companies):
                matched.append(m)
        meetings = matched
        
    data_dir = ensure_data_dir("data/raw_fathom")
    fetched = []
    
    # We do a second pass to inject the matched company name into the raw json
    # so that the rules parser doesn't have to guess it blindly from the text.
    from .db import list_companies
    rows = list_companies(settings.database_url)
    known_companies_raw = [r['canonical_name'] for r in rows] if rows else []
    
    from .vehicles import canonicalize_company_name
    
    summary_path = ""
    for item in meetings:
        normalized = normalize_fathom_meeting(item)
        
        title = (item.get('title') or '').lower()
        matched_company = None
        for company in known_companies_raw:
            if company.lower() in title:
                matched_company = canonicalize_company_name(company)
                break
                
        if matched_company:
            normalized['company_name_hint'] = matched_company
            
        mid = normalized['gmail_message_id']
        path = data_dir / f"{mid}.json"
        write_json(path, normalized)
        summary["fetched"] += 1
        fetched.append({
            'fathom_id': mid,
            'title': item.get('title'),
            'company': matched_company,
            'recorded_by': normalized['from_address'],
            'date': normalized['received_at'],
            'path': str(path)
        })
    summary_path = _write_stage_summary(
        data_dir,
        summary,
        extra={"source": "fathom", "output_dir": str(data_dir)},
    )
    print(json.dumps({"count": len(fetched), "meetings": fetched}, indent=2))
    print(json.dumps({"event": "stage_summary", "path": summary_path, "stage": "fathom_fetch"}))
    return 0

def cmd_gmail_fetch(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    cfg = GmailClientConfig(
        client_secret_file=settings.google_oauth_client_secret_file,
        token_file=settings.google_oauth_token_file,
        service_account_file=settings.google_service_account_file,
        service_account_subject=settings.google_service_account_subject,
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
    summary = _new_stage_summary("gmail_fetch")
    summary_path = ""
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
        summary["fetched"] += 1
        fetched.append({
            "gmail_message_id": normalized["gmail_message_id"],
            "subject": normalized["subject"],
            "from_address": normalized["from_address"],
            "received_at": normalized["received_at"],
            "attachment_count": len(saved_attachments),
            "path": str(data_dir / f"{item['id']}.json"),
        })

    summary_path = _write_stage_summary(
        data_dir,
        summary,
        extra={"query": settings.gmail_query, "output_dir": str(data_dir)},
    )
    print(json.dumps({
        "query": settings.gmail_query,
        "count": len(fetched),
        "messages": fetched,
    }, indent=2))
    print(json.dumps({"event": "stage_summary", "path": summary_path, "stage": "gmail_fetch"}))
    return 0


def cmd_parse_raw(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    provider = get_parse_provider(settings)
    raw_dir = ensure_data_dir("data/raw_gmail")
    out_dir = ensure_data_dir("data/parsed_updates")
    provider_out_dir = ensure_data_dir(f"data/provider_outputs/{provider.name}")
    fathom_dir = ensure_data_dir("data/raw_fathom")
    sources = []
    if args.source in ('all', 'gmail'):
        sources.extend(sorted(raw_dir.glob("*.json")))
    if args.source in ('all', 'fathom'):
        sources.extend(sorted(fathom_dir.glob("*.json")))
    raw_files = sorted(sources, key=lambda f: f.name)[: args.limit]
    parsed: list[dict] = []
    summary = _new_stage_summary("parse_raw")
    summary_path = ""
    parse_error: Exception | None = None
    for path in raw_files:
        try:
            raw = load_raw_message(path)
            raw['source_path'] = str(path)
            bundle = build_source_bundle(raw)
            raw['attachment_text'] = bundle.attachment_text
            result = provider.parse(raw)
            update = result.update
            update['attachment_count'] = bundle.attachment_count
            update['attachment_text_present'] = bundle.attachment_text_present
            update['parse_provider'] = provider.name
            write_json(out_dir / path.name, update)
            if result.provider_output is not None:
                write_json(provider_out_dir / path.name, result.provider_output)
            parsed.append({
                'gmail_message_id': update['gmail_message_id'],
                'company_name': update['company_name'],
                'report_period_label': update['report_period_label'],
                'parser_provider': update.get('parser_provider', provider.name),
                'path': str(out_dir / path.name),
            })
            summary["parsed"] += 1
            if args.throttle_seconds > 0:
                time.sleep(args.throttle_seconds)
        except Exception as exc:
            summary["failed"] += 1
            _increment_reason(summary, "failed_reasons", "parse_failure")
            parse_error = exc
            break
    summary_path = _write_stage_summary(
        out_dir,
        summary,
        extra={"provider": provider.name, "source": args.source, "output_dir": str(out_dir)},
    )
    print(json.dumps({'count': len(parsed), 'provider': provider.name, 'updates': parsed}, indent=2))
    print(json.dumps({"event": "stage_summary", "path": summary_path, "stage": "parse_raw"}))
    if parse_error is not None:
        raise parse_error
    return 0


def cmd_bem_sample_run(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    provider_name = (args.provider or settings.parse_provider or 'bem').lower()
    provider_settings = replace(settings, parse_provider=provider_name)
    provider = get_parse_provider(provider_settings)

    sample_path = Path(args.sample_file).expanduser()
    if not sample_path.exists():
        raise FileNotFoundError(f'Sample file not found: {sample_path}')
    samples = json.loads(sample_path.read_text())
    if not isinstance(samples, list):
        raise ValueError(f'Sample file must be a list, got {type(samples)}')

    raw_dir = ensure_data_dir('data/raw_gmail')
    sample_root = ensure_data_dir(Path('data') / 'provider_samples' / provider.name)
    parsed_dir = ensure_data_dir(sample_root / 'parsed')
    provider_out_dir = ensure_data_dir(sample_root / 'provider_output')

    summary: list[dict] = []
    missing: list[str] = []
    for entry in samples:
        if not isinstance(entry, dict):
            continue
        message_id = entry.get('gmail_message_id')
        if not message_id:
            continue
        raw_path = raw_dir / f"{message_id}.json"
        if not raw_path.exists():
            missing.append(message_id)
            continue
        raw = load_raw_message(raw_path)
        raw['source_path'] = str(raw_path)
        bundle = build_source_bundle(raw)
        raw['attachment_text'] = bundle.attachment_text
        result = provider.parse(raw)
        update = result.update
        update['attachment_count'] = bundle.attachment_count
        update['attachment_text_present'] = bundle.attachment_text_present
        parsed_path = parsed_dir / f"{message_id}.json"
        write_json(parsed_path, update)

        provider_output_path = None
        if result.provider_output is not None:
            provider_output_path = provider_out_dir / f"{message_id}.json"
            write_json(provider_output_path, result.provider_output)

        summary.append({
            'gmail_message_id': message_id,
            'company_hint': entry.get('company'),
            'company_detected': update.get('company_name'),
            'metrics_count': len(update.get('metrics_json', {})),
            'highlights_count': len(update.get('highlights_json', [])),
            'asks_count': len(update.get('asks_json', [])),
            'risks_count': len(update.get('risks_json', [])),
            'parsed_path': str(parsed_path),
            'provider_output_path': str(provider_output_path) if provider_output_path else None,
        })

    print(json.dumps({
        'provider': provider.name,
        'samples_requested': len(samples),
        'samples_parsed': len(summary),
        'missing_raw_messages': missing,
        'results': summary,
    }, indent=2))
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
    fathom_dir = ensure_data_dir('data/raw_fathom')
    parsed_dir = ensure_data_dir('data/parsed_updates')
    parsed_files = sorted(parsed_dir.glob('*.json'))
    if args.source == 'gmail':
        parsed_files = [p for p in parsed_files if not p.name.startswith('fathom_')]
    elif args.source == 'fathom':
        parsed_files = [p for p in parsed_files if p.name.startswith('fathom_')]
    parsed_files = parsed_files[: args.limit]
    synced: list[dict] = []
    summary = _new_stage_summary("sync_postgres")
    summary_path = ""

    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            for parsed_path in parsed_files:
                summary["parsed"] += 1
                parsed = load_raw_message(parsed_path)
                raw_path = raw_dir / parsed_path.name
                if not raw_path.exists():
                    alt_path = fathom_dir / parsed_path.name
                    if alt_path.exists():
                        raw_path = alt_path
                    else:
                        summary["skipped"] += 1
                        _increment_reason(summary, "skip_reasons", "raw_source_missing")
                        continue
                raw = load_raw_message(raw_path)
                company_id = None
                if parsed.get('company_name'):
                    company_id = upsert_company(cur, parsed['company_name'])
                email_message_id = upsert_email_message(cur, raw)
                update_id = upsert_quarterly_update(cur, email_message_id, company_id, parsed)
                if update_id is not None:
                    synced.append({
                        'gmail_message_id': parsed.get('gmail_message_id'),
                        'company_name': parsed.get('company_name'),
                        'email_message_id': email_message_id,
                        'quarterly_update_id': update_id,
                    })
                else:
                    summary["skipped"] += 1
                    if not parsed.get('company_name'):
                        _increment_reason(summary, "skip_reasons", "no_company_match")
                    else:
                        has_content = any(
                            bool(parsed.get(field))
                            for field in ("summary", "highlights_json", "asks_json", "risks_json", "metrics_json")
                        )
                        if not has_content:
                            _increment_reason(summary, "skip_reasons", "empty_content")
                        else:
                            _increment_reason(summary, "skip_reasons", "not_persisted")
        conn.commit()

    summary_path = _write_stage_summary(
        parsed_dir,
        summary,
        extra={"source": args.source, "input_dir": str(parsed_dir)},
    )
    print(json.dumps({'count': len(synced), 'synced': synced}, indent=2))
    print(json.dumps({"event": "stage_summary", "path": summary_path, "stage": "sync_postgres"}))
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


def cmd_run_pipeline(args: argparse.Namespace) -> int:
    print("=== Running Full Pipeline ===")
    
    print("\n--- 1. Fetching Fathom Meetings ---")
    ret = cmd_fathom_fetch(args)
    if ret != 0:
        print("Warning: Fathom fetch failed or incomplete.")
        
    print("\n--- 2. Fetching Gmail Updates ---")
    ret = cmd_gmail_fetch(args)
    if ret != 0:
        print("Warning: Gmail fetch failed or incomplete.")
        
    print("\n--- 3. Parsing Raw Data (Gmail + Fathom) ---")
    ret = cmd_parse_raw(args)
    if ret != 0: return ret
    
    print("\n--- 4. Syncing to Postgres ---")
    ret = cmd_sync_postgres(args)
    if ret != 0: return ret
    
    print("\n--- 5. Generating Reports ---")
    ret = cmd_generate_report(args)
    
    print("\n=== Pipeline Complete ===")
    return ret

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

    p = sub.add_parser("fathom-fetch", help="fetch recent Fathom meetings as pseudo-updates")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--title-match", help="Only import meetings with this substring in the title")
    p.add_argument("--company-match", action="store_true", help="Only import meetings whose title contains a known company name from Postgres")
    p.add_argument("--created-after", help="ISO timestamp (e.g. 2025-12-01T00:00:00Z) to filter meetings")
    p.set_defaults(func=cmd_fathom_fetch)

    p = sub.add_parser("gmail-fetch", help="fetch raw Gmail messages for the configured query")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_gmail_fetch)

    p = sub.add_parser("parse-raw", help="parse fetched raw Gmail messages into normalized update JSON")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--source", choices=['all', 'gmail', 'fathom'], default='all', help="Which raw source directory to parse")
    p.add_argument("--throttle-seconds", type=float, default=0.0, help="Seconds to sleep between parses (avoid API rate limits)")
    p.set_defaults(func=cmd_parse_raw)

    p = sub.add_parser("bem-sample-run", help="run the parse provider on the curated BEM eval set")
    p.add_argument("--sample-file", default="samples/bem_eval_samples.json", help="path to the Gmail id list")
    p.add_argument("--provider", choices=["bem", "hybrid", "rules"], default="bem")
    p.set_defaults(func=cmd_bem_sample_run)

    p = sub.add_parser("db-apply", help="apply Postgres schema")
    p.set_defaults(func=cmd_db_apply)

    p = sub.add_parser("sync-postgres", help="sync parsed updates into Postgres")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--source", choices=['all', 'gmail', 'fathom'], default='all', help="Only sync parsed files from this source")
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

    p = sub.add_parser("run-pipeline", help="run the complete pipeline (fathom + gmail -> parse -> sync -> report)")
    p.add_argument("--limit", type=int, default=0, help="limit for fetching and parsing (0 for no limit)")
    p.add_argument("--title-match", default=None, help="Only import meetings with this substring in the title")
    p.add_argument("--company-match", action="store_true", help="Only import meetings whose title contains a known company name from Postgres")
    p.add_argument("--created-after", default=None, help="ISO timestamp (e.g. 2025-12-01T00:00:00Z) to filter meetings")
    p.add_argument("--source", choices=['all', 'gmail', 'fathom'], default='all', help="which source to parse/sync")
    p.add_argument("--throttle-seconds", type=float, default=0.0, help="Seconds to sleep between parses")
    p.add_argument("--provider", choices=["bem", "hybrid", "rules"], default="hybrid", help="which provider to use for parsing")
    p.set_defaults(func=cmd_run_pipeline)

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
