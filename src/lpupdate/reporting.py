from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from .store import iter_data_record_json_files
from .vehicles import company_vehicle_type, vehicles_for_company


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    return value.strip('-') or 'unknown'


def fmt_metric_value(value: Any) -> str:
    if isinstance(value, dict):
        if 'value' in value:
            base = f"{value['value']:,.0f}" if isinstance(value['value'], (int, float)) else str(value['value'])
            if value.get('currency') == 'USD':
                base = f"${base}"
            if value.get('period'):
                base += f" ({value['period']})"
            return base
        if 'low' in value and 'high' in value:
            low = f"{value['low']:,.0f}" if isinstance(value['low'], (int, float)) else str(value['low'])
            high = f"{value['high']:,.0f}" if isinstance(value['high'], (int, float)) else str(value['high'])
            if value.get('currency') == 'USD':
                low = f"${low}"
                high = f"${high}"
            return f"{low} – {high}"
        if 'previous_value' in value and 'current_value' in value:
            prev = f"{value['previous_value']:,.0f}" if isinstance(value['previous_value'], (int, float)) else str(value['previous_value'])
            curr = f"{value['current_value']:,.0f}" if isinstance(value['current_value'], (int, float)) else str(value['current_value'])
            if value.get('currency') == 'USD':
                prev = f"${prev}"
                curr = f"${curr}"
            return f"{prev} → {curr}"
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return ', '.join(str(v) for v in value)
    if isinstance(value, float):
        return f"{value:,.2f}" if not value.is_integer() else f"{value:,.0f}"
    return str(value)


def render_metrics(metrics: dict[str, Any]) -> str:
    if not metrics:
        return '<p>No structured metrics extracted yet.</p>'
    items = []
    for key, value in metrics.items():
        label = key.replace('_', ' ').title()
        items.append(f"<tr><th>{html.escape(label)}</th><td>{html.escape(fmt_metric_value(value))}</td></tr>")
    return '<table class="metrics">' + ''.join(items) + '</table>'


def render_list(items: list[str]) -> str:
    cleaned = [i for i in items if i and i.strip()]
    if not cleaned:
        return '<p>None extracted.</p>'
    return '<ul>' + ''.join(f'<li>{html.escape(i)}</li>' for i in cleaned) + '</ul>'


def render_vehicle_badges(vehicles: list[str]) -> str:
    if not vehicles:
        return '<span class="small">No vehicle mapping yet.</span>'
    items = []
    for vehicle in vehicles:
        kind = company_vehicle_type(vehicle)
        class_name = 'vehicle-fund' if kind == 'fund' else 'vehicle-spv'
        items.append(f'<span class="vehicle-pill {class_name}">{html.escape(vehicle)}</span>')
    return ''.join(items)


def record_source_type(record: dict[str, Any]) -> str:
    message_id = str(record.get('gmail_message_id') or '').lower()
    return 'fathom' if message_id.startswith('fathom_') else 'gmail'


def build_report_summary(record: dict[str, Any], slug: str) -> dict[str, Any]:
    return {
        'report_id': record.get('gmail_message_id'),
        'period_label': record.get('report_period_label'),
        'received_at': record.get('received_at'),
        'subject': record.get('subject'),
        'detail_path': f"startups/{slug}/{report_filename(record)}",
        'source_type': record_source_type(record),
    }


def build_startup_payload(company: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sort_records_desc(records)
    slug = slugify(company)
    vehicles = ordered[0].get('vehicles_json') or vehicles_for_company(company)
    reports = [build_report_summary(rec, slug) for rec in ordered]
    latest = reports[0] if reports else None
    return {
        'slug': slug,
        'canonical_name': company,
        'investment_vehicles': vehicles,
        'latest_report': latest,
        'reports': reports,
    }


def received_at_sort_key(value: Any) -> datetime:
    text = str(value or '').strip()
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def sort_records_desc(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda r: (
            received_at_sort_key(r.get('received_at')),
            str(r.get('gmail_message_id') or ''),
        ),
        reverse=True,
    )


def report_filename(record: dict[str, Any]) -> str:
    message_id = slugify(str(record.get('gmail_message_id') or 'unknown-message'))
    period = slugify(str(record.get('report_period_label') or 'report'))
    return f'{message_id}-{period}.html'


def render_report_page(record: dict[str, Any], company_page_href: str = '../index.html') -> str:
    company = record.get('company_name') or 'Unknown'
    summary = record.get('summary') or 'No summary available.'
    metrics = record.get('metrics_json') or {}
    highlights = record.get('highlights_json') or []
    asks = record.get('asks_json') or []
    risks = record.get('risks_json') or []
    vehicles = record.get('vehicles_json') or vehicles_for_company(company)
    return f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(company)} — {html.escape(str(record.get('report_period_label') or 'Report'))}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; max-width: 900px; line-height: 1.5; }}
    h1, h2 {{ color: #16324f; }}
    .meta {{ color: #555; margin-bottom: 24px; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin: 18px 0; }}
    table.metrics {{ width: 100%; border-collapse: collapse; }}
    table.metrics th, table.metrics td {{ border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }}
    table.metrics th {{ width: 32%; background: #f7f7f7; }}
    .small {{ font-size: 0.92em; color: #666; }}
    .vehicle-pill {{ display: inline-block; margin: 4px 8px 0 0; padding: 6px 10px; border-radius: 999px; font-size: 0.92em; font-weight: 600; }}
    .vehicle-fund {{ background: #e8f1ff; color: #16324f; }}
    .vehicle-spv {{ background: #eef8ea; color: #245c2a; }}
  </style>
</head>
<body>
  <p><a href="{html.escape(company_page_href)}">← Back to {html.escape(company)} reports</a></p>
  <h1>{html.escape(company)}</h1>
  <div class="meta">
    <div><strong>Report period:</strong> {html.escape(str(record.get('report_period_label') or 'Unknown'))}</div>
    <div><strong>Received at:</strong> {html.escape(str(record.get('received_at') or 'Unknown'))}</div>
    <div><strong>Subject:</strong> {html.escape(str(record.get('subject') or 'Unknown'))}</div>
    <div><strong>Gmail message id:</strong> {html.escape(str(record.get('gmail_message_id') or 'Unknown'))}</div>
    <div><strong>Attachment text present:</strong> {html.escape(str(record.get('attachment_text_present', False)))}</div>
    <div><strong>Investment vehicles:</strong> {render_vehicle_badges(vehicles)}</div>
  </div>

  <div class="card">
    <h2>Summary</h2>
    <p>{html.escape(summary)}</p>
  </div>

  <div class="card">
    <h2>Key Metrics</h2>
    {render_metrics(metrics)}
  </div>

  <div class="card">
    <h2>Highlights</h2>
    {render_list(highlights)}
  </div>

  <div class="card">
    <h2>Asks</h2>
    {render_list(asks)}
  </div>

  <div class="card">
    <h2>Risks</h2>
    {render_list(risks)}
  </div>
</body>
</html>
'''


def render_company_page(company: str, records: list[dict[str, Any]]) -> str:
    ordered = sort_records_desc(records)
    latest = ordered[0]
    vehicles = latest.get('vehicles_json') or vehicles_for_company(company)
    rows = []
    for rec in ordered:
        rows.append(
            f"<tr>"
            f"<td><a href='{html.escape(report_filename(rec))}'>{html.escape(str(rec.get('report_period_label') or 'Unknown'))}</a></td>"
            f"<td>{html.escape(str(rec.get('received_at') or 'Unknown'))}</td>"
            f"<td>{html.escape(str(rec.get('subject') or 'Unknown'))}</td>"
            f"<td>{html.escape(str(rec.get('gmail_message_id') or 'Unknown'))}</td>"
            f"</tr>"
        )
    return f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(company)} — lpupdate reports</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; max-width: 1100px; line-height: 1.5; }}
    h1, h2 {{ color: #16324f; }}
    .meta {{ color: #555; margin-bottom: 24px; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin: 18px 0; }}
    .small {{ font-size: 0.92em; color: #666; }}
    .vehicle-pill {{ display: inline-block; margin: 4px 8px 0 0; padding: 6px 10px; border-radius: 999px; font-size: 0.92em; font-weight: 600; }}
    .vehicle-fund {{ background: #e8f1ff; color: #16324f; }}
    .vehicle-spv {{ background: #eef8ea; color: #245c2a; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f6fb; }}
  </style>
</head>
<body>
  <p><a href="../index.html">← Back to startup index</a></p>
  <h1>{html.escape(company)}</h1>
  <div class="meta">
    <div><strong>Total parsed reports:</strong> {len(ordered)}</div>
    <div><strong>Latest report period:</strong> {html.escape(str(latest.get('report_period_label') or 'Unknown'))}</div>
    <div><strong>Latest received at:</strong> {html.escape(str(latest.get('received_at') or 'Unknown'))}</div>
    <div><strong>Investment vehicles:</strong> {render_vehicle_badges(vehicles)}</div>
  </div>

  <div class="card">
    <h2>Reports</h2>
    <p class="small">Newest first. Click any row's period to open the full report.</p>
    <table>
      <thead>
        <tr><th>Report Period</th><th>Received At</th><th>Subject</th><th>Gmail Message ID</th></tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </div>
</body>
</html>
'''


def render_summary_cards(cards: list[tuple[str, int]]) -> str:
    parts = []
    for label, value in cards:
        parts.append(
            f'''<div class="summary-card"><div class="summary-card-label">{html.escape(label)}</div><div class="summary-card-value">{value}</div></div>'''
        )
    return '<section class="summary-grid">' + ''.join(parts) + '</section>'


def render_vehicle_group(title: str, records: list[dict[str, Any]]) -> str:
    if not records:
        return ''
    rows = []
    for rec in sorted(records, key=lambda r: (r.get('company_name') or '').lower()):
        company = rec.get('company_name') or 'Unknown'
        slug = slugify(company)
        vehicles = rec.get('vehicles_json') or vehicles_for_company(company)
        rows.append(
            f"<tr><td><a href='startups/{slug}/index.html'>{html.escape(company)}</a></td>"
            f"<td>{render_vehicle_badges(vehicles)}</td>"
            f"<td>{html.escape(str(rec.get('report_period_label') or 'Unknown'))}</td>"
            f"<td>{html.escape(str(rec.get('received_at') or 'Unknown'))}</td>"
            f"<td>{html.escape(str(rec.get('subject') or 'Unknown'))}</td></tr>"
        )
    return f'''<section class="vehicle-section">
  <h2>{html.escape(title)}</h2>
  <table>
    <thead>
      <tr><th>Startup</th><th>Vehicles</th><th>Latest Period</th><th>Received At</th><th>Subject</th></tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</section>'''


def render_index(records: list[dict[str, Any]]) -> str:
    enriched = []
    for rec in records:
        enriched.append({**rec, 'vehicles_json': rec.get('vehicles_json') or vehicles_for_company(rec.get('company_name'))})

    fund_i_records = [rec for rec in enriched if 'BuenTrip Ventures Fund I' in (rec.get('vehicles_json') or [])]
    fund_ii_records = [rec for rec in enriched if 'BuenTrip Ventures Fund II' in (rec.get('vehicles_json') or [])]
    spv_records = [rec for rec in enriched if any(company_vehicle_type(vehicle) == 'spv' for vehicle in (rec.get('vehicles_json') or []))]
    unmapped_records = [rec for rec in enriched if not (rec.get('vehicles_json') or [])]

    summary_cards = [
        ('Total startups', len(enriched)),
        ('Fund I startups', len(fund_i_records)),
        ('Fund II startups', len(fund_ii_records)),
        ('SPV-backed startups', len(spv_records)),
        ('Unmapped startups', len(unmapped_records)),
    ]

    return f'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>lpupdate startup report index</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; max-width: 1200px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f6fb; }}
    .vehicle-section {{ margin-top: 28px; }}
    .vehicle-pill {{ display: inline-block; margin: 4px 8px 0 0; padding: 6px 10px; border-radius: 999px; font-size: 0.9em; font-weight: 600; }}
    .vehicle-fund {{ background: #e8f1ff; color: #16324f; }}
    .vehicle-spv {{ background: #eef8ea; color: #245c2a; }}
    .summary {{ color: #4b5563; max-width: 900px; }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 20px 0 8px; }}
    .summary-card {{ border: 1px solid #dbe4f0; border-radius: 12px; padding: 16px; background: #f8fbff; }}
    .summary-card-label {{ font-size: 0.9em; color: #526172; margin-bottom: 6px; }}
    .summary-card-value {{ font-size: 1.8em; font-weight: 700; color: #16324f; }}
  </style>
</head>
<body>
  <h1>lpupdate — Latest Startup Reports</h1>
  <p class="summary">Click a startup to open its report history. Each startup page lists every parsed investor update in reverse chronological order, and each report opens on its own detail page.</p>
  {render_summary_cards(summary_cards)}
  {render_vehicle_group('BuenTrip Ventures Fund I', fund_i_records)}
  {render_vehicle_group('BuenTrip Ventures Fund II', fund_ii_records)}
  {render_vehicle_group('SPVs', spv_records)}
  {render_vehicle_group('Unmapped startups', unmapped_records)}
</body>
</html>
'''




def export_json_site(out_dir: Path, startups: list[dict[str, Any]]) -> None:
    if not startups:
        return
    generated_at = datetime.now(timezone.utc).isoformat()
    vehicle_groups: dict[str, list[dict[str, Any]]] = {}
    overview_startups: list[dict[str, Any]] = []

    for startup in startups:
        summary = {
            'slug': startup['slug'],
            'canonical_name': startup['canonical_name'],
            'investment_vehicles': startup['investment_vehicles'],
            'latest_report': startup['latest_report'],
            'reports': startup['reports'],
        }
        overview_startups.append(summary)
        vehicles = startup['investment_vehicles'] or ['Unmapped']
        for vehicle in vehicles:
            vehicle_groups.setdefault(vehicle, []).append(summary)

    overview_payload = {
        'generated_at': generated_at,
        'vehicle_groups': [
            {'title': title, 'startups': vehicle_groups[title]}
            for title in sorted(vehicle_groups.keys())
        ],
    }
    (out_dir / 'index.json').write_text(json.dumps(overview_payload, indent=2))

    for startup in startups:
        startup_payload = {
            'startup': {
                'slug': startup['slug'],
                'canonical_name': startup['canonical_name'],
                'investment_vehicles': startup['investment_vehicles'],
                'latest_report': startup['latest_report'],
                'report_count': len(startup['reports']),
            },
            'reports': startup['reports'],
        }
        startup_dir = out_dir / 'startups' / startup['slug']
        startup_dir.mkdir(parents=True, exist_ok=True)
        (startup_dir / 'index.json').write_text(json.dumps(startup_payload, indent=2))


def latest_by_company(parsed_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for rec in parsed_records:
        company = rec.get('company_name') or 'Unknown'
        prev = latest.get(company)
        if prev is None or received_at_sort_key(rec.get('received_at')) > received_at_sort_key(prev.get('received_at')):
            latest[company] = rec
    return list(latest.values())


def records_by_company(parsed_records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for rec in parsed_records:
        company = rec.get('company_name') or 'Unknown'
        grouped.setdefault(company, []).append(rec)
    return grouped


def generate_report_site(parsed_dir: str | Path, out_dir: str | Path) -> dict[str, Any]:
    parsed_dir = Path(parsed_dir)
    out_dir = Path(out_dir)
    startup_dir = out_dir / 'startups'
    startup_dir.mkdir(parents=True, exist_ok=True)

    parsed_records = [json.loads(p.read_text()) for p in iter_data_record_json_files(parsed_dir)]
    latest_records = latest_by_company(parsed_records)
    grouped_records = records_by_company(parsed_records)

    report_count = 0
    startup_payloads: list[dict[str, Any]] = []
    for company, records in grouped_records.items():
        slug = slugify(company)
        company_dir = startup_dir / slug
        company_dir.mkdir(parents=True, exist_ok=True)
        (company_dir / 'index.html').write_text(render_company_page(company, records))
        for rec in records:
            (company_dir / report_filename(rec)).write_text(render_report_page(rec))
            report_count += 1
        startup_payloads.append(build_startup_payload(company, records))

    (out_dir / 'index.html').write_text(render_index(latest_records))
    export_json_site(out_dir, startup_payloads)
    return {
        'company_count': len(latest_records),
        'report_count': report_count,
        'index_path': str(out_dir / 'index.html'),
        'startup_dir': str(startup_dir),
    }
