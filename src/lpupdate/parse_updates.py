from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
}


SECTION_ALIASES = {
    'highlights': ['Key updates', 'Highlights', 'Highlights & Product', 'Key Events', 'What did we DO last month?'],
    'asks': ['How you can help', 'Asks', 'Thanks and Asks', '👍 How can you help?', '🙏 Asks'],
    'risks': ['Risks', 'The Bad', '🔴 The Bad: Strategic Consolidation'],
}


def load_raw_message(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def _clean_company_name(value: str | None) -> str | None:
    if not value:
        return None
    name = value.strip(' –-|:')
    name = re.sub(r'\bQ[1-4][-\s]?20?\d{2,4}\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
    name = re.sub(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
    name = re.sub(r'\bInvestor Update\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
    name = re.sub(r'\bMonthly Update\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
    return name or None


def infer_company(subject: str | None, body_text: str | None) -> str | None:
    text = subject or ''
    patterns = [
        r'Fwd:\s*([^:]+):\s*Q\d',
        r'Fwd:\s*([^|\-]+?)\s*[–\-:]\s*Investor Update',
        r'Fwd:\s*([^|\-]+?)\s*[–\-:]\s*Monthly Update',
        r'Fwd:\s*([^|\-]+?)\s+Investor Update',
        r'Fwd:\s*([^|\-]+?)\s+Monthly Update',
        r'([^|\-]+?)\s+Investor Update',
        r'([^|\-]+?)\s+Monthly Update',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return _clean_company_name(m.group(1))
    if body_text:
        m = re.search(r'Subject:\s*([^:]+):\s*Q\d', body_text, re.IGNORECASE)
        if m:
            return _clean_company_name(m.group(1))
    return None


def infer_period(subject: str | None, body_text: str | None) -> dict[str, Any]:
    text = ' '.join(filter(None, [subject, body_text[:2000] if body_text else None]))
    quarter_match = re.search(r'Q([1-4])[-\s]?(?:20)?(\d{2,4})', text, re.IGNORECASE)
    if quarter_match:
        q = int(quarter_match.group(1))
        y = quarter_match.group(2)
        year = int(y) if len(y) == 4 else 2000 + int(y)
        return {
            'report_period_label': f'Q{q} {year}',
            'report_quarter': q,
            'report_year': year,
            'report_month': None,
        }
    month_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})', text, re.IGNORECASE)
    if month_match:
        month_name = month_match.group(1).lower()
        year = int(month_match.group(2))
        return {
            'report_period_label': f'{month_match.group(1)} {year}',
            'report_quarter': None,
            'report_year': year,
            'report_month': MONTHS[month_name],
        }
    return {
        'report_period_label': None,
        'report_quarter': None,
        'report_year': None,
        'report_month': None,
    }


def _money_number(value: str) -> float:
    cleaned = value.replace('US$', '').replace('$', '').replace(',', '').replace('+', '').replace('~', '').strip().lower()
    mult = 1
    if cleaned.endswith('mm'):
        mult = 1_000_000
        cleaned = cleaned[:-2]
    elif cleaned.endswith('m'):
        mult = 1_000_000
        cleaned = cleaned[:-1]
    elif cleaned.endswith('k'):
        mult = 1_000
        cleaned = cleaned[:-1]
    return float(cleaned) * mult


def extract_metrics(body_text: str | None) -> dict[str, Any]:
    text = (body_text or '').replace('*', '')
    metrics: dict[str, Any] = {}

    patterns = {
        'cash': r'Cash(?: at (?:the end of the month|Bank))?\s*:\s*~?\s*(?:US\$|\$)?([\d,]+(?:\.\d+)?[mk]?)',
        'monthly_cash_burn': r'(?:Monthly|Net) cash burn.*?:\s*~?\s*(?:US\$|\$)?([\d,]+(?:\.\d+)?[mk]?)',
        'runway_months': r'(?:Implied runway|Cash Runway|Runway)\s*:\s*~?\s*(\d+(?:\.\d+)?)\s*(?:months?|x)?',
        'revenue_current': r'revenues? from \$([\d,.]+[mk]?) to \$([\d,.]+[mk]?)',
        'gross_profit_current': r'gross profit from ~?\$([\d,.]+[mk]?) to ~?\$([\d,.]+[mk]?)',
        'adj_ebitda_range': r'generating \$([\d,.]+[mk]?)\s*[-–]\s*([\d,.]+[mk]?) of adj\. EBITDA',
        'adj_ebitda_single': r'generating \$([\d,.]+[mk]?)\+? of adj\. EBITDA',
        'arr': r'\$([\d,.]+(?:\.\d+)?[mk]?)\s*ARR',
        'mrr': r'\$([\d,.]+(?:\.\d+)?[mk]?)\s*MRR',
        'net_revenue': r'\$([\d,.]+(?:\.\d+)?[mk]?)\+?/yr of net\s+revenue',
        'annual_revenue_range': r'\$([\d,.]+(?:\.\d+)?)([mk]?)\s*[-–]\s*\$([\d,.]+(?:\.\d+)?)([mk]?)\+? in annual revenue',
        'gross_profit_range': r'\$([\d,.]+(?:\.\d+)?)([mk]?)\s*[-–]\s*\$([\d,.]+(?:\.\d+)?)([mk]?)\s*gross profit',
        'gross_margin_percent': r'(\d+(?:\.\d+)?)%\s+increase in gross margin',
        'ebitda_per_load_percent': r'(\d+(?:\.\d+)?)%\s+EBITDA per load increase',
        'cost_to_serve_percent': r'(\d+(?:\.\d+)?)%\s+reduction in cost to serve',
        'ai_sourced_shipments_percent': r'(\d+(?:\.\d+)?)% of shipments\s+had a bid sourced',
        'ai_booked_loads_percent': r'(\d+(?:\.\d+)?)% of all loads are fully sourced, negotiated, and booked',
        'active_clients': r'(\d+(?:,\d+)*)\s+active clients',
        'loads_month1': r'(\d+(?:\+)?)\s+loads in month 1',
        'headcount_hires': r'We hired\s+(\d+)\s+new engineers',
    }

    metric_aliases = {
        'mrr': ('mrr', 'money', 'monthly'),
        'arr': ('arr', 'money', 'annual'),
        'annualized run rate': ('arr', 'money', 'annual'),
        'q4 revenue generated': ('quarter_revenue', 'money', 'quarterly'),
        'revenue to date': ('revenue_to_date', 'money', None),
        'gross margin': ('gross_margin_percent', 'percent', None),
        'growth run rate': ('growth_run_rate_percent', 'percent', None),
        'customers & pilots': ('customers_and_pilots', 'int', None),
        'customers and pilots': ('customers_and_pilots', 'int', None),
        'countries active': ('countries_active', 'int', None),
        'gmv managed': ('gmv_managed', 'money', None),
        'documents processed': ('documents_processed', 'int', None),
        'suppliers': ('suppliers', 'int', None),
        'cash at the end of the month': ('cash', 'money', None),
        'cash at bank': ('cash', 'money', None),
        'net cash burn': ('monthly_cash_burn', 'money', 'monthly'),
        'runway': ('runway_months', 'float', None),
        'cash runway': ('runway_months', 'float', None),
        'churn rate': ('churn_rate_percent', 'percent', None),
        'cac inbound': ('cac_inbound', 'money', None),
        'accumulated roas 2025': ('roas_2025', 'float', None),
        'active clients': ('active_clients', 'int', None),
        'impressions': ('impressions', 'int', None),
        'video views': ('video_views', 'int', None),
        'comments': ('comments_count', 'int', None),
        'saves': ('saves_count', 'int', None),
        'dm sends': ('dm_sends', 'int', None),
    }

    def parse_money(value: str) -> dict[str, Any] | None:
        m = re.search(r'(?:US\$|\$)\s*([\d,]+(?:\.\d+)?\s*(?:mm|m|k)?)', value, re.IGNORECASE)
        if not m:
            return None
        return {'value': _money_number(m.group(1).replace(' ', '')), 'currency': 'USD'}

    def parse_percent(value: str) -> float | None:
        m = re.search(r'([+-]?\d+(?:\.\d+)?)\s*%', value)
        return float(m.group(1)) if m else None

    def parse_int(value: str) -> int | None:
        m = re.search(r'([\d,]+)', value)
        return int(m.group(1).replace(',', '')) if m else None

    def parse_float(value: str) -> float | None:
        m = re.search(r'([\d,]+(?:\.\d+)?)', value)
        return float(m.group(1).replace(',', '')) if m else None

    def set_metric_from_alias(label: str, raw_value: str):
        normalized = re.sub(r'\s+', ' ', label.strip().lower())
        alias = metric_aliases.get(normalized)
        if not alias or alias[0] in metrics:
            return
        key, kind, period = alias
        if kind == 'money':
            parsed = parse_money(raw_value)
            if parsed:
                if period:
                    parsed['period'] = period
                metrics[key] = parsed
        elif kind == 'percent':
            parsed = parse_percent(raw_value)
            if parsed is not None:
                metrics[key] = parsed
        elif kind == 'int':
            parsed = parse_int(raw_value)
            if parsed is not None:
                metrics[key] = parsed
        elif kind == 'float':
            parsed = parse_float(raw_value)
            if parsed is not None:
                metrics[key] = parsed

    for line in text.splitlines():
        cleaned = line.strip().lstrip('-•').strip()
        if not cleaned or ':' not in cleaned:
            continue
        label, raw_value = cleaned.split(':', 1)
        set_metric_from_alias(label, raw_value.strip())

    def set_money(name: str, match_key: str, period: str | None = None):
        m = re.search(patterns[match_key], text, re.IGNORECASE)
        if m and name not in metrics:
            payload = {'value': _money_number(m.group(1)), 'currency': 'USD'}
            if period:
                payload['period'] = period
            metrics[name] = payload

    set_money('cash', 'cash')
    set_money('monthly_cash_burn', 'monthly_cash_burn', period='monthly')
    set_money('arr', 'arr', period='annual')
    set_money('mrr', 'mrr', period='monthly')
    set_money('net_revenue', 'net_revenue', period='annual')

    m = re.search(patterns['runway_months'], text, re.IGNORECASE)
    if m and 'runway_months' not in metrics:
        metrics['runway_months'] = float(m.group(1))

    m = re.search(patterns['revenue_current'], text, re.IGNORECASE)
    if m:
        metrics['revenue'] = {
            'previous_value': _money_number(m.group(1)),
            'current_value': _money_number(m.group(2)),
            'currency': 'USD',
        }

    m = re.search(patterns['gross_profit_current'], text, re.IGNORECASE)
    if m:
        metrics['gross_profit'] = {
            'previous_value': _money_number(m.group(1)),
            'current_value': _money_number(m.group(2)),
            'currency': 'USD',
        }

    m = re.search(patterns['annual_revenue_range'], text, re.IGNORECASE)
    if m:
        low_num, low_sfx, high_num, high_sfx = m.groups()
        if not low_sfx and high_sfx:
            low_sfx = high_sfx
        metrics['annual_revenue_range'] = {
            'low': _money_number(low_num + low_sfx),
            'high': _money_number(high_num + high_sfx),
            'currency': 'USD',
        }

    m = re.search(patterns['gross_profit_range'], text, re.IGNORECASE)
    if m:
        low_num, low_sfx, high_num, high_sfx = m.groups()
        if not low_sfx and high_sfx:
            low_sfx = high_sfx
        metrics['gross_profit_range'] = {
            'low': _money_number(low_num + low_sfx),
            'high': _money_number(high_num + high_sfx),
            'currency': 'USD',
        }

    m = re.search(patterns['adj_ebitda_range'], text, re.IGNORECASE)
    if m:
        metrics['adj_ebitda_expected'] = {
            'low': _money_number(m.group(1)),
            'high': _money_number(m.group(2)),
            'currency': 'USD',
        }
    else:
        m = re.search(patterns['adj_ebitda_single'], text, re.IGNORECASE)
        if m:
            metrics['adj_ebitda_expected'] = {
                'value': _money_number(m.group(1)),
                'currency': 'USD',
            }

    def set_percent(name: str, key: str):
        m = re.search(patterns[key], text, re.IGNORECASE)
        if m and name not in metrics:
            metrics[name] = float(m.group(1))

    set_percent('gross_margin_increase_percent', 'gross_margin_percent')
    set_percent('ebitda_per_load_increase_percent', 'ebitda_per_load_percent')
    set_percent('cost_to_serve_reduction_percent', 'cost_to_serve_percent')
    set_percent('ai_sourced_shipments_percent', 'ai_sourced_shipments_percent')
    set_percent('ai_booked_loads_percent', 'ai_booked_loads_percent')

    m = re.search(patterns['active_clients'], text, re.IGNORECASE)
    if m and 'active_clients' not in metrics:
        metrics['active_clients'] = int(m.group(1).replace(',', ''))

    m = re.search(patterns['loads_month1'], text, re.IGNORECASE)
    if m:
        metrics['loads_month1'] = int(m.group(1).replace('+', ''))

    m = re.search(patterns['headcount_hires'], text, re.IGNORECASE)
    if m:
        metrics['new_engineers_hired'] = int(m.group(1))

    yoy_matches = re.findall(r'(\d+(?:\.\d+)?)%\s+YoY', text, re.IGNORECASE)
    if yoy_matches:
        metrics['yoy_percentages'] = [float(x) for x in yoy_matches]

    return metrics


def _section_text(body_text: str | None, heading: str, stop_headings: list[str] | None = None, window: int = 5000) -> str:
    text = body_text or ''
    idx = text.lower().find(heading.lower())
    if idx == -1:
        return ''
    section = text[idx: idx + window]
    if stop_headings:
        lower_section = section.lower()
        cut_positions = []
        for stop in stop_headings:
            pos = lower_section.find(stop.lower(), len(heading))
            if pos != -1:
                cut_positions.append(pos)
        if cut_positions:
            section = section[: min(cut_positions)]
    return section


def _extract_first_section(body_text: str | None, headings: list[str], stop_headings: list[str] | None = None) -> str:
    for heading in headings:
        section = _section_text(body_text, heading, stop_headings=stop_headings)
        if section:
            return section
    return ''


def extract_bullets_after_heading(body_text: str | None, heading: str, stop_headings: list[str] | None = None) -> list[str]:
    section = _section_text(body_text, heading, stop_headings=stop_headings)
    if not section:
        return []
    bullets = re.findall(r'\n\s*[-•]\s*(.+)', section)
    cleaned = []
    for bullet in bullets[:30]:
        item = bullet.strip()
        if item in {'-', '*', ''}:
            continue
        cleaned.append(item)
    return cleaned[:12]


def extract_section_paragraphs(body_text: str | None, heading: str, stop_headings: list[str] | None = None) -> list[str]:
    section = _section_text(body_text, heading, stop_headings=stop_headings)
    if not section:
        return []
    lines = [line.strip() for line in section.splitlines()]
    out = []
    started = False
    for line in lines:
        if not started:
            if heading.lower() in line.lower():
                started = True
            continue
        if not line:
            continue
        if line.startswith(('-', '•')):
            out.append(line.lstrip('-• ').strip())
            continue
        if len(line) > 40 and not re.match(r'^[A-Z][a-z]+:', line):
            out.append(line)
    deduped = []
    for line in out:
        if line not in deduped:
            deduped.append(line)
    return deduped[:12]


def extract_section_by_aliases(body_text: str | None, aliases: list[str], stop_headings: list[str]) -> list[str]:
    for heading in aliases:
        section = _section_text(body_text, heading, stop_headings=stop_headings)
        if not section:
            continue
        bullets = re.findall(r'\n\s*[-•]\s*(.+)', section)
        cleaned = []
        for item in bullets[:30]:
            item = item.strip()
            if item and item not in {'-', '*'}:
                cleaned.append(item)
        if cleaned:
            return cleaned[:12]
        paragraphs = extract_section_paragraphs(body_text, heading, stop_headings=stop_headings)
        if paragraphs:
            return paragraphs[:12]
    return []


def summarize(body_text: str | None) -> str:
    text = (body_text or '').strip()
    if not text:
        return ''
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    useful = [line for line in lines if len(line) > 40][:5]
    return ' '.join(useful)[:1200]


def normalize_update(raw: dict[str, Any]) -> dict[str, Any]:
    subject = raw.get('subject')
    body_text = raw.get('body_text') or ''
    attachment_text = raw.get('attachment_text') or ''
    combined_text = '\n\n'.join(part for part in [body_text, attachment_text] if part)
    period = infer_period(subject, combined_text)
    metrics = extract_metrics(combined_text)
    stop_headings = [
        'How you can help', 'Runway', 'Learn more', 'Asks', 'Thanks and Asks',
        'Fundraising & Financing', 'Product and Technology', 'Key Events', 'Team & Culture',
    ]
    highlights = extract_section_by_aliases(combined_text, SECTION_ALIASES['highlights'], stop_headings)
    asks = extract_section_by_aliases(combined_text, SECTION_ALIASES['asks'], ['Runway', 'Learn more', 'Blurbs to facilitate connections'])
    risks = extract_section_by_aliases(combined_text, SECTION_ALIASES['risks'], ['How you can help', 'Asks', 'Thanks and Asks'])
    return {
        'gmail_message_id': raw.get('gmail_message_id'),
        'gmail_thread_id': raw.get('gmail_thread_id'),
        'company_name': infer_company(subject, body_text),
        'subject': subject,
        'from_address': raw.get('from_address'),
        'to_addresses': raw.get('to_addresses', []),
        'received_at': raw.get('received_at'),
        **period,
        'summary': summarize(combined_text),
        'metrics_json': metrics,
        'highlights_json': highlights,
        'asks_json': asks,
        'risks_json': risks,
        'people_json': [],
        'source_path': raw.get('source_path'),
        'parser_version': 'v2',
    }
