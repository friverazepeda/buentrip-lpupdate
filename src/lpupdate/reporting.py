from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

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


def render_company_page(record: dict[str, Any]) -> str:
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
  <title>{html.escape(company)} — lpupdate report</title>
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
  <p><a href="../index.html">← Back to startup index</a></p>
  <h1>{html.escape(company)}</h1>
  <div class="meta">
    <div><strong>Latest report period:</strong> {html.escape(str(record.get('report_period_label') or 'Unknown'))}</div>
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

  <p class="small">Generated from the latest parsed update in lpupdate.</p>
</body>
</html>
'''


def render_vehicle_group(title: str, records: list[dict[str, Any]]) -> str:
    if not records:
        return ''
    rows = []
    for rec in sorted(records, key=lambda r: (r.get('company_name') or '').lower()):
        company = rec.get('company_name') or 'Unknown'
        slug = slugify(company)
        vehicles = rec.get('vehicles_json') or vehicles_for_company(company)
        rows.append(
            f"<tr><td><a href='startups/{slug}.html'>{html.escape(company)}</a></td>"
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
  </style>
</head>
<body>
  <h1>lpupdate — Latest Startup Reports</h1>
  <p class="summary">One page per startup based on the latest parsed investor update. Startups are grouped by investment vehicle so you can quickly review Fund I, Fund II, and SPV coverage.</p>
  {render_vehicle_group('BuenTrip Ventures Fund I', fund_i_records)}
  {render_vehicle_group('BuenTrip Ventures Fund II', fund_ii_records)}
  {render_vehicle_group('SPVs', spv_records)}
  {render_vehicle_group('Unmapped startups', unmapped_records)}
</body>
</html>
'''


def latest_by_company(parsed_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for rec in parsed_records:
        company = rec.get('company_name') or 'Unknown'
        prev = latest.get(company)
        if prev is None or str(rec.get('received_at') or '') > str(prev.get('received_at') or ''):
            latest[company] = rec
    return list(latest.values())


def generate_report_site(parsed_dir: str | Path, out_dir: str | Path) -> dict[str, Any]:
    parsed_dir = Path(parsed_dir)
    out_dir = Path(out_dir)
    startup_dir = out_dir / 'startups'
    startup_dir.mkdir(parents=True, exist_ok=True)

    parsed_records = [json.loads(p.read_text()) for p in sorted(parsed_dir.glob('*.json'))]
    latest_records = latest_by_company(parsed_records)

    for rec in latest_records:
        slug = slugify(rec.get('company_name') or 'unknown')
        (startup_dir / f'{slug}.html').write_text(render_company_page(rec))

    (out_dir / 'index.html').write_text(render_index(latest_records))
    return {
        'company_count': len(latest_records),
        'index_path': str(out_dir / 'index.html'),
        'startup_dir': str(startup_dir),
    }
