from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .vehicles import canonicalize_company_name

MONTH_PATTERN = r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'

MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


SECTION_ALIASES = {
    'highlights': ['Key updates', 'Highlights', 'Highlights & Product', 'Key Events', 'What did we DO last month?', 'Investor Update – Q4', '🏆 Achievements', '📈 Traction', 'TLDR'],
    'asks': ['How you can help', 'Asks', 'Thanks and Asks', '👍 How can you help?', '🙏 Asks', 'Blurbs to facilitate connections you can help us with'],
    'risks': ['Risks', 'The Bad', '🔴 The Bad: Strategic Consolidation', '🏋 Challenges', 'Update on Fundraising / Lowlights and Focus Areas'],
}


SECTION_START_HINTS = [
    'key updates', 'highlights', 'kpi', 'kpi’s', "kpi's", 'runway', 'debt & finance',
    'debt & financing', 'fundraising', 'operations', 'tech', 'peru monthly kpi',
    'mexico monthly kpi', 'leasy kpi', 'investor update – q4', 'investor update - q4',
]


SECTION_END_HINTS = [
    'how you can help', 'asks', 'thanks and asks', 'learn more', 'wrapped & founders reflection',
    'wrapped -', 'finance comments', 'budget analysis', 'financials q4', 'onwards,',
    'thank you for your continued support', '--', 'frivera@buentrip.vc',
]


CONFIDENCE_HIGH = 0.95
CONFIDENCE_MEDIUM = 0.8
CONFIDENCE_LOW = 0.6


def load_raw_message(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def _clean_company_name(value: str | None) -> str | None:
    if not value:
        return None
    name = value.strip(' –-|:')
    name = re.sub(r'\bQ[1-4][-\s]?20?\d{2,4}\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
    name = re.sub(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
    name = re.sub(r'\bInvestor/Internal Update\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
    name = re.sub(r'\bInvestor Update\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
    name = re.sub(r'\bMonthly Update\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
    name = re.sub(r'\bBOD Update\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
    name = re.sub(r'\[[^\]]+\]', '', name).strip(' –-|:')
    return name or None


def infer_company(subject: str | None, body_text: str | None) -> str | None:
    text = subject or ''
    patterns = [
        r'Fwd:\s*([^:]+):\s*Q\d',
        r'Fwd:\s*([^|\-]+?)\s*[–\-:]\s*Investor/Internal Update',
        r'Fwd:\s*([^|\-]+?)\s*[–\-:]\s*Investor Update',
        r'Fwd:\s*([^|\-]+?)\s*[–\-:]\s*Monthly Update',
        r'Fwd:\s*([^|\-]+?)\s*[–\-:]\s*BOD Update',
        r'Fwd:\s*([^|\-]+?)\s+Investor Update',
        r'Fwd:\s*([^|\-]+?)\s+Monthly Update',
        r'Fwd:\s*([^|\-]+?)\s+BOD Update',
        r'([^|\-]+?)\s+Investor Update',
        r'([^|\-]+?)\s+Monthly Update',
        r'([^|\-]+?)\s+BOD Update',
        r'Fwd:\s*([^x]+?)\s+x\s+BTV\s+review',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return _clean_company_name(m.group(1))
    if body_text:
        m = re.search(r'Subject:\s*([^:]+):\s*Q\d', body_text, re.IGNORECASE)
        if m:
            return _clean_company_name(m.group(1))
        m = re.search(r'From:\s+[^<]+<[^>]+@([a-z0-9-]+)\.', body_text, re.IGNORECASE)
        if m:
            return _clean_company_name(m.group(1).replace('-', ' ').title().replace(' ', ''))
    return None


def infer_period(subject: str | None, body_text: str | None) -> dict[str, Any]:
    text = ' '.join(filter(None, [subject, body_text[:4000] if body_text else None]))
    quarter_match = re.search(r'\bQ([1-4])(?:[-\s]?(20\d{2}|\d{2}))\b', text, re.IGNORECASE)
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
    quarter_subject_match = re.search(r'\bQ([1-4])\b', subject or '', re.IGNORECASE)
    forward_date_match = re.search(r'Date:\s+\w+,\s+(' 
        r'January|February|March|April|May|June|July|August|September|October|November|December' 
        r'|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{1,2},\s+(20\d{2})', body_text or '', re.IGNORECASE)
    if quarter_subject_match and forward_date_match:
        q = int(quarter_subject_match.group(1))
        month_token = forward_date_match.group(1).lower()[:3]
        month_map = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
        year = int(forward_date_match.group(2))
        month_num = month_map[month_token]
        if month_num <= 3:
            year -= 1
        return {
            'report_period_label': f'Q{q} {year}',
            'report_quarter': q,
            'report_year': year,
            'report_month': None,
        }
    range_match = re.search(rf'{MONTH_PATTERN}\s+\d{{1,2}}\s*[-–]\s+{MONTH_PATTERN}\s+\d{{1,2}}\s*(20\d{{2}})', text, re.IGNORECASE)
    if range_match:
        start_month = MONTHS[range_match.group(1).lower()]
        end_month_name = range_match.group(2).lower()
        year = int(range_match.group(3))
        end_month = MONTHS[end_month_name]
        quarter = (end_month - 1) // 3 + 1
        return {
            'report_period_label': f'Q{quarter} {year}',
            'report_quarter': quarter,
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


def _normalize_text(text: str | None) -> str:
    value = text or ''
    value = value.replace('\r\n', '\n').replace('\r', '\n')
    value = value.replace('\u202f', ' ').replace('\xa0', ' ')
    value = value.replace('–', '-').replace('—', '-')
    value = value.replace('“', '"').replace('”', '"').replace('’', "'")
    value = re.sub(r'\*+', '', value)
    value = re.sub(r'[ \t]+', ' ', value)
    value = re.sub(r'\n{3,}', '\n\n', value)
    return value.strip()


def _cleanup_section_text(text: str) -> str:
    value = _normalize_text(text)
    value = re.sub(r'<https?://[^>]+>', '', value)
    value = re.sub(r'https?://\S+', '', value)
    value = re.sub(r'\[image:[^\]]+\]', '', value, flags=re.IGNORECASE)
    value = re.sub(r'^>{2,}.*$', '', value, flags=re.MULTILINE)
    value = re.sub(r'^\s*Demonstração\s*$', '', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\s*Sent via Paperstreet.*$', '', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\s*Paperstreet ©.*$', '', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\s*No longer wish to hear from us\?.*$', '', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\s*Calendly link\s*$', '', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\s*Schedule time with me!?\s*$', '', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\s*SPA:\s*$', '', value, flags=re.MULTILINE)
    value = re.sub(r'^\s*ENG:\s*$', '', value, flags=re.MULTILINE)
    value = re.sub(r'^\*?Confidential\..*$', '', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\*?This update and its contents are confidential.*$', '', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\*?Blurbs to facilitate connections you can help us with:?\*?$', 'How you can help', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\*?Update on Fundraising / Lowlights and Focus Areas:?\*?$', 'Risks', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\*?🏋 Challenges\*?$', 'Risks', value, flags=re.MULTILINE)
    value = re.sub(r'^\*?📈 Looking Ahead\*?$', 'Looking Ahead', value, flags=re.MULTILINE)
    value = re.sub(r'^\*?Looking Ahead\*?$', 'Looking Ahead', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\*?📈 Traction\*?$', 'Highlights', value, flags=re.MULTILINE)
    value = re.sub(r'^\*?🏆 Achievements\*?$', 'Highlights', value, flags=re.MULTILINE)
    value = re.sub(r'^\*?Highlights:?\*?$', 'Highlights', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\*?Risks:?\*?$', 'Risks', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\*?How you can help:?\*?$', 'How you can help', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^\*?Asks:?\*?$', 'How you can help', value, flags=re.MULTILINE | re.IGNORECASE)
    value = re.sub(r'^[*_\-\s]{20,}$', '', value, flags=re.MULTILINE)
    value = re.sub(r'\n{3,}', '\n\n', value)
    return value.strip()


def _strip_signature(text: str) -> str:
    thread_match = re.search(r'\nOn [A-Za-z]{3,9}, .*? wrote:', text, flags=re.IGNORECASE | re.DOTALL)
    if thread_match:
        text = text[:thread_match.start()]
    patterns = [
        r'\n--\s*\n.*$',
        r'\nOnwards,.*$',
        r'\nThank you for your continued support,.*$',
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    return text


def _relevant_metric_text(text: str) -> str:
    return _cleanup_section_text(text)


def _line_snippet(text: str, start: int, end: int, window: int = 220) -> str:
    snippet = text[max(0, start - window): min(len(text), end + window)]
    snippet = snippet.replace('\n', ' ').strip()
    snippet = re.sub(r'\s+', ' ', snippet)
    return snippet[:400]


def _set_metric(metrics: dict[str, Any], confidence: dict[str, Any], name: str, value: Any, snippet: str, score: float, origin: str) -> None:
    if name in metrics:
        return
    metrics[name] = value
    confidence[name] = {
        'score': score,
        'origin': origin,
        'source_snippet': snippet,
    }


def _parse_money_value(raw_value: str, currency: str = 'USD', period: str | None = None) -> dict[str, Any]:
    payload = {'value': _money_number(raw_value), 'currency': currency}
    if period:
        payload['period'] = period
    return payload


def extract_metrics(body_text: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    text = _relevant_metric_text(body_text or '')
    metrics: dict[str, Any] = {}
    confidence: dict[str, Any] = {}

    metric_aliases = {
        'mrr': ('mrr', 'money', 'monthly', 'USD'),
        'a.r.r': ('arr', 'money', 'annual', 'USD'),
        'arr': ('arr', 'money', 'annual', 'USD'),
        'annualized run rate': ('arr', 'money', 'annual', 'USD'),
        'q4 revenue generated': ('quarter_revenue', 'money', 'quarterly', 'USD'),
        'revenue to date': ('revenue_to_date', 'money', None, 'USD'),
        'gross margin': ('gross_margin_percent', 'percent', None, None),
        'growth run rate': ('growth_run_rate_percent', 'percent', None, None),
        'customers & pilots': ('customers_and_pilots', 'int', None, None),
        'customers and pilots': ('customers_and_pilots', 'int', None, None),
        'countries active': ('countries_active', 'int', None, None),
        'gmv managed': ('gmv_managed', 'money', None, 'USD'),
        'documents processed': ('documents_processed', 'int', None, None),
        'suppliers': ('suppliers', 'int', None, None),
        'cash at the end of the month': ('cash', 'money', None, 'USD'),
        'cash at bank': ('cash', 'money', None, 'USD'),
        'cash': ('cash', 'money', None, 'USD'),
        'net cash burn': ('monthly_cash_burn', 'money', 'monthly', 'USD'),
        'monthly cash burn': ('monthly_cash_burn', 'money', 'monthly', 'USD'),
        'runway': ('runway_months', 'float', None, None),
        'cash runway': ('runway_months', 'float', None, None),
        'churn rate': ('churn_rate_percent', 'percent', None, None),
        'cac inbound': ('cac_inbound', 'money', None, 'USD'),
        'accumulated roas 2025': ('roas_2025', 'float', None, None),
        'active clients': ('active_clients', 'int', None, None),
        'impressions': ('impressions', 'int', None, None),
        'video views': ('video_views', 'int', None, None),
        'comments': ('comments_count', 'int', None, None),
        'saves': ('saves_count', 'int', None, None),
        'dm sends': ('dm_sends', 'int', None, None),
        'avg. down payment': ('avg_down_payment', 'money', None, 'USD'),
        'time to evaluate': ('time_to_evaluate_hours', 'hours', None, None),
        'time of evaluation': ('time_to_evaluate_hours', 'hours', None, None),
        'time to deliver car': ('time_to_deliver_car_days', 'days', None, None),
        'customer cycle': ('customer_cycle_days', 'days', None, None),
        'team size': ('team_size', 'int', None, None),
        'new contracts': ('new_contracts', 'int', None, None),
        'pre-approved capital': ('pre_approved_capital', 'money', None, 'USD'),
        'drawn capital': ('drawn_capital', 'money', None, 'USD'),
        'gross revenue': ('gross_revenue', 'money', None, 'USD'),
        'ebitda': ('ebitda', 'money', None, 'USD'),
        'december revenue': ('december_revenue', 'money', None, 'USD'),
        'total revenue 2025': ('revenue_2025', 'money', None, 'USD'),
        'gmv 2025': ('gmv_2025', 'money', None, 'USD'),
        'cash on hand': ('cash', 'money', None, 'USD'),
        'total quarterly revenue': ('quarter_revenue', 'money', 'quarterly', 'USD'),
    }

    def parse_money(raw_value: str, currency: str = 'USD', period: str | None = None) -> dict[str, Any] | None:
        m = re.search(r'(?:US\$|\$)\s*([\d,]+(?:\.\d+)?\s*(?:mm|m|k)?)', raw_value, re.IGNORECASE)
        if not m:
            return None
        return _parse_money_value(m.group(1).replace(' ', ''), currency=currency, period=period)

    def parse_percent(raw_value: str) -> float | None:
        m = re.search(r'([+-]?\d+(?:\.\d+)?)\s*%', raw_value)
        return float(m.group(1)) if m else None

    def parse_int(raw_value: str) -> int | None:
        m = re.search(r'([\d,]+)', raw_value)
        return int(m.group(1).replace(',', '')) if m else None

    def parse_float(raw_value: str) -> float | None:
        m = re.search(r'([\d,]+(?:\.\d+)?)', raw_value)
        return float(m.group(1).replace(',', '')) if m else None

    def parse_hours(raw_value: str) -> float | None:
        m = re.search(r'(\d+(?:\.\d+)?)\s*hours?', raw_value, re.IGNORECASE)
        return float(m.group(1)) if m else None

    def parse_days(raw_value: str) -> float | None:
        m = re.search(r'(\d+(?:\.\d+)?)\s*days?', raw_value, re.IGNORECASE)
        return float(m.group(1)) if m else None

    for line in text.splitlines():
        cleaned = line.strip().lstrip('-•').strip()
        if not cleaned or ':' not in cleaned:
            continue
        label, raw_value = cleaned.split(':', 1)
        normalized = re.sub(r'\s+', ' ', label.strip().lower())
        alias = metric_aliases.get(normalized)
        if not alias:
            continue
        key, kind, period, currency = alias
        if key in metrics:
            continue
        if kind == 'money':
            parsed = parse_money(raw_value, currency=currency or 'USD', period=period)
        elif kind == 'percent':
            parsed = parse_percent(raw_value)
        elif kind == 'int':
            parsed = parse_int(raw_value)
        elif kind == 'float':
            parsed = parse_float(raw_value)
        elif kind == 'hours':
            parsed = parse_hours(raw_value)
        elif kind == 'days':
            parsed = parse_days(raw_value)
        else:
            parsed = None
        if parsed is not None:
            _set_metric(metrics, confidence, key, parsed, cleaned, CONFIDENCE_HIGH, 'labeled_line')

    regex_specs = [
        ('cash', r'Cash(?: at (?:the end of the month|Bank))?\s*:\s*~?\s*(?:US\$|\$)?([\d,]+(?:\.\d+)?[mk]?)', lambda m: _parse_money_value(m.group(1)), CONFIDENCE_HIGH, 'runway_section'),
        ('monthly_cash_burn', r'(?:Monthly|Net) cash burn.*?:\s*~?\s*(?:US\$|\$)?([\d,]+(?:\.\d+)?[mk]?)', lambda m: _parse_money_value(m.group(1), period='monthly'), CONFIDENCE_HIGH, 'runway_section'),
        ('runway_months', r'(?:Implied runway|Cash Runway|Runway)\s*:\s*~?\s*(\d+(?:\.\d+)?)\s*(?:months?|x)?', lambda m: float(m.group(1)), CONFIDENCE_HIGH, 'runway_section'),
        ('revenue', r'revenues? from \$([\d,.]+[mk]?) to \$([\d,.]+[mk]?)', lambda m: {'previous_value': _money_number(m.group(1)), 'current_value': _money_number(m.group(2)), 'currency': 'USD'}, CONFIDENCE_MEDIUM, 'narrative_growth'),
        ('gross_profit', r'gross profit from ~?\$([\d,.]+[mk]?) to ~?\$([\d,.]+[mk]?)', lambda m: {'previous_value': _money_number(m.group(1)), 'current_value': _money_number(m.group(2)), 'currency': 'USD'}, CONFIDENCE_MEDIUM, 'narrative_growth'),
        ('annual_revenue_range', r'\$([\d,.]+(?:\.\d+)?)([mk]?)\s*-\s*\$([\d,.]+(?:\.\d+)?)([mk]?)\+? in annual revenue', lambda m: {'low': _money_number(m.group(1) + (m.group(2) or m.group(4))), 'high': _money_number(m.group(3) + (m.group(4) or m.group(2))), 'currency': 'USD'}, CONFIDENCE_LOW, 'transaction_scenario'),
        ('gross_profit_range', r'\$([\d,.]+(?:\.\d+)?)([mk]?)\s*-\s*\$([\d,.]+(?:\.\d+)?)([mk]?)\s*gross profit', lambda m: {'low': _money_number(m.group(1) + (m.group(2) or m.group(4))), 'high': _money_number(m.group(3) + (m.group(4) or m.group(2))), 'currency': 'USD'}, CONFIDENCE_LOW, 'transaction_scenario'),
        ('adj_ebitda_expected', r'generating \$([\d,.]+[mk]?)\s*-\s*([\d,.]+[mk]?) of adj\. EBITDA', lambda m: {'low': _money_number(m.group(1)), 'high': _money_number(m.group(2)), 'currency': 'USD'}, CONFIDENCE_LOW, 'forward_looking'),
        ('adj_ebitda_expected', r'generating \$([\d,.]+[mk]?)\+? of adj\. EBITDA', lambda m: {'value': _money_number(m.group(1)), 'currency': 'USD'}, CONFIDENCE_LOW, 'forward_looking'),
        ('gross_margin_increase_percent', r'(\d+(?:\.\d+)?)%\s+increase in gross margin', lambda m: float(m.group(1)), CONFIDENCE_MEDIUM, 'operational_case_study'),
        ('ebitda_per_load_increase_percent', r'(\d+(?:\.\d+)?)%\s+EBITDA per load increase', lambda m: float(m.group(1)), CONFIDENCE_MEDIUM, 'operational_case_study'),
        ('cost_to_serve_reduction_percent', r'(\d+(?:\.\d+)?)%\s+reduction in cost to serve', lambda m: float(m.group(1)), CONFIDENCE_MEDIUM, 'operational_case_study'),
        ('ai_sourced_shipments_percent', r'(\d+(?:\.\d+)?)% of shipments\s+had a bid sourced', lambda m: float(m.group(1)), CONFIDENCE_MEDIUM, 'operational_case_study'),
        ('ai_booked_loads_percent', r'(\d+(?:\.\d+)?)% of (?:all loads|shipments) (?:are|were) fully sourced, negotiated, and booked', lambda m: float(m.group(1)), CONFIDENCE_MEDIUM, 'operational_case_study'),
        ('new_engineers_hired', r'We hired\s+(\d+)\s+new engineers', lambda m: int(m.group(1)), CONFIDENCE_MEDIUM, 'narrative_hiring'),
        ('active_clients', r'\b(\d+(?:,\d+)*)\s+active clients\b', lambda m: int(m.group(1).replace(',', '')), CONFIDENCE_HIGH, 'headline_kpi'),
        ('gross_revenue', r'Gross Revenue:\s*(?:[A-Z]{3}\d{2}\s*:)?\s*([\d.]+[mk]?)\s*USD', lambda m: _parse_money_value(m.group(1)), CONFIDENCE_HIGH, 'headline_kpi'),
        ('ebitda', r'EBITDA\s*(?:[A-Z]{3}\d{2})?\s*([\d.]+[mk]?)\s*USD', lambda m: _parse_money_value(m.group(1)), CONFIDENCE_HIGH, 'headline_kpi'),
        ('mrr', r'MRR of\s*([\d.]+[mk]?)\s*USD', lambda m: _parse_money_value(m.group(1), period='monthly'), CONFIDENCE_HIGH, 'headline_kpi'),
        ('december_revenue', r'December Revenue:\s*\$([\d,]+(?:\.\d+)?)', lambda m: _parse_money_value(m.group(1)), CONFIDENCE_HIGH, 'headline_kpi'),
        ('revenue_2025', r'Total Revenue 2025:\s*\$([\d,.]+[mk]?)', lambda m: _parse_money_value(m.group(1)), CONFIDENCE_HIGH, 'headline_kpi'),
        ('gmv_2025', r'GMV 2025:\s*\$([\d,.]+[mk]?)', lambda m: _parse_money_value(m.group(1)), CONFIDENCE_HIGH, 'headline_kpi'),
        ('arr', r'Total ARR EoQ:\s*\$([\d,.]+[mk]?)\s*USD', lambda m: _parse_money_value(m.group(1), period='annual'), CONFIDENCE_HIGH, 'headline_kpi'),
        ('quarter_revenue', r'Total Quarterly Revenue:\s*\$([\d,.]+[mk]?)\s*USD', lambda m: _parse_money_value(m.group(1), period='quarterly'), CONFIDENCE_HIGH, 'headline_kpi'),
        ('runway_months', r'Runway:\s*(\d+(?:\.\d+)?)\s*months', lambda m: float(m.group(1)), CONFIDENCE_HIGH, 'headline_kpi'),
        ('burn_multiple', r'Burn Multiple:\s*(\d+(?:\.\d+)?)', lambda m: float(m.group(1)), CONFIDENCE_MEDIUM, 'headline_kpi'),
        ('borrowers_enabled_monthly', r'Total Unique Borrowers Enabled / Month:\s*([\d,.]+[mk]?)', lambda m: int(_money_number(m.group(1))), CONFIDENCE_HIGH, 'headline_kpi'),
        ('ndr_percent', r'\b(\d+(?:\.\d+)?)%\s*NDR\b', lambda m: float(m.group(1)), CONFIDENCE_MEDIUM, 'headline_kpi'),
        ('pmf_score_percent', r'Sean Ellis PMF survey.*?achieved a\s*(\d+(?:\.\d+)?)%\s*score', lambda m: float(m.group(1)), CONFIDENCE_MEDIUM, 'headline_kpi'),
        ('bookings', r'\$([\d,.]+[mk]?)\s+in bookings', lambda m: _parse_money_value(m.group(1)), CONFIDENCE_HIGH, 'headline_kpi'),
        ('sales_demo_conversion_percent', r'(\d+(?:\.\d+)?)% of leads who see a live demo', lambda m: float(m.group(1)), CONFIDENCE_MEDIUM, 'headline_kpi'),
    ]

    for name, pattern, builder, score, origin in regex_specs:
        if name in metrics:
            continue
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        _set_metric(metrics, confidence, name, builder(m), _line_snippet(text, m.start(), m.end()), score, origin)

    leasy_table_patterns = [
        ('arr', r'A\.R\.R\s*\n\$([\d,.]+[mk]?)', lambda m: _parse_money_value(m.group(1), period='annual'), CONFIDENCE_HIGH, 'kpi_deck'),
        ('pre_approved_capital', r'Pre-Approved Capital\s*Drawn capital\s*\n\$([\d,.]+[mk]?)\$([\d,.]+[mk]?)', lambda m: _parse_money_value(m.group(1)), CONFIDENCE_HIGH, 'kpi_deck'),
        ('drawn_capital', r'Pre-Approved Capital\s*Drawn capital\s*\n\$([\d,.]+[mk]?)\$([\d,.]+[mk]?)', lambda m: _parse_money_value(m.group(2)), CONFIDENCE_HIGH, 'kpi_deck'),
        ('new_contracts', r'New Contracts\s*\n\(\+[^\n]+\)\s*\n\+?(\d+(?:,\d+)*)', lambda m: int(m.group(1).replace(',', '')), CONFIDENCE_HIGH, 'kpi_deck'),
        ('team_size', r'Team Size\s*\n\(\+[^\n]+\)\s*\n(\d+(?:,\d+)*)', lambda m: int(m.group(1).replace(',', '')), CONFIDENCE_HIGH, 'kpi_deck'),
        ('cash', r'over \$([\d,.]+[mk]?) in our cash account', lambda m: _parse_money_value(m.group(1)), CONFIDENCE_HIGH, 'finance_section'),
        ('avg_down_payment', r'Avg\. Down Payment:\s*\$([\d,.]+)', lambda m: _parse_money_value(m.group(1)), CONFIDENCE_HIGH, 'kpi_line_item'),
        ('time_to_evaluate_hours', r'Time to Evaluate:\s*(\d+(?:\.\d+)?)\s*hours?', lambda m: float(m.group(1)), CONFIDENCE_HIGH, 'kpi_line_item'),
        ('time_to_deliver_car_days', r'Time to Deliver Car\*?:\s*(\d+(?:\.\d+)?)\s*days?', lambda m: float(m.group(1)), CONFIDENCE_HIGH, 'kpi_line_item'),
        ('customer_cycle_days', r'Customer Cycle:\s*(\d+(?:\.\d+)?)\s*days?', lambda m: float(m.group(1)), CONFIDENCE_HIGH, 'kpi_line_item'),
    ]

    for name, pattern, builder, score, origin in leasy_table_patterns:
        if name in metrics:
            continue
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if not m:
            continue
        _set_metric(metrics, confidence, name, builder(m), _line_snippet(text, m.start(), m.end()), score, origin)

    yoy_matches = re.findall(r'(\d+(?:\.\d+)?)%\s+YoY', text, re.IGNORECASE)
    if yoy_matches and 'yoy_percentages' not in metrics:
        metrics['yoy_percentages'] = [float(x) for x in yoy_matches]
        confidence['yoy_percentages'] = {
            'score': CONFIDENCE_LOW,
            'origin': 'narrative_growth',
            'source_snippet': ' '.join(re.findall(r'.{0,60}\d+(?:\.\d+)?%\s+YoY.{0,60}', text, re.IGNORECASE)[:2])[:400],
        }

    return metrics, confidence


def _section_text(body_text: str | None, heading: str, stop_headings: list[str] | None = None, window: int = 5000) -> str:
    text = _cleanup_section_text(body_text or '')
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
        if not line or set(line) <= {'-'}:
            continue
        if line.startswith(('-', '•')):
            item = line.lstrip('-• ').strip()
            if item and set(item) != {'-'}:
                out.append(item)
            continue
        if len(line) > 40 and not re.match(r'^[A-Z][a-z]+:', line):
            out.append(line)
    deduped = []
    for line in out:
        line = re.sub(r'\s+', ' ', line).strip()
        if not line or line in deduped or set(line) <= {'-'}:
            continue
        if len(line) < 12:
            continue
        if line.lower() in {'highlights', 'risks', 'how you can help'}:
            continue
        if line.startswith('http') or line.startswith('<http'):
            continue
        deduped.append(line)
    return deduped[:12]


def extract_section_by_aliases(body_text: str | None, aliases: list[str], stop_headings: list[str]) -> list[str]:
    for heading in aliases:
        section = _section_text(body_text, heading, stop_headings=stop_headings)
        if not section:
            continue
        bullets = re.findall(r'\n\s*[-•]\s*(.+)', section)
        cleaned = []
        for item in bullets[:40]:
            item = re.sub(r'\s+', ' ', item).strip()
            if not item or item in {'-', '*'} or set(item) == {'-'}:
                continue
            if len(item) < 12:
                continue
            if item.startswith('http') or item.startswith('<http'):
                continue
            cleaned.append(item)
        if cleaned:
            return cleaned[:12]
        paragraphs = extract_section_paragraphs(body_text, heading, stop_headings=stop_headings)
        if paragraphs:
            return paragraphs[:12]
    return []


def summarize(body_text: str | None) -> str:
    text = _cleanup_section_text(body_text or '')
    if not text:
        return ''
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    useful = [line for line in lines if len(line) > 40 and 'Forwarded message' not in line][:5]
    return ' '.join(useful)[:1200]


def _filter_section_items(items: list[str], kind: str) -> list[str]:
    filtered: list[str] = []
    banned_substrings = {
        'asks': ['provides ai-driven lending infrastructure', 'paperstreet', 'all rights reserved', 'no longer wish to hear from us'],
        'risks': ['audit report', 'auditor:', 'management\'s responsibility', 'financial amounts are expressed', 'timely and complete provision'],
    }
    for item in items:
        text = re.sub(r'\s+', ' ', item).strip(' -•')
        if not text or len(text) < 12:
            continue
        lower = text.lower()
        if lower in {'highlights', 'risks', 'how you can help'}:
            continue
        if text in filtered:
            continue
        if kind == 'asks' and ('calendly' in lower or 'book with andrés' in lower or 'book with andres' in lower):
            continue
        if kind == 'asks' and lower.startswith('altscore investor/internal update'):
            continue
        if kind == 'risks' and any(token in lower for token in ['auditor', 'audit report', 'management\'s responsibility', 'documentary support']):
            continue
        if kind == 'risks' and lower.startswith('●'):
            continue
        if kind == 'risks' and ('board of directors' in lower or 'brazilian accounting standards' in lower or 'nbc (' in lower):
            continue
        if any(token in lower for token in banned_substrings.get(kind, [])):
            continue
        filtered.append(text)
    return filtered[:12]


def normalize_update(raw: dict[str, Any]) -> dict[str, Any]:
    subject = raw.get('subject')
    body_text = raw.get('body_text') or ''
    attachment_text = raw.get('attachment_text') or ''
    cleaned_body_text = _strip_signature(_cleanup_section_text(body_text))
    cleaned_attachment_text = _cleanup_section_text(attachment_text)
    combined_text = '\n\n'.join(part for part in [cleaned_body_text, cleaned_attachment_text] if part)
    period = infer_period(subject, combined_text)
    metrics, confidence = extract_metrics(combined_text)
    stop_headings = [
        'How you can help', 'Runway', 'Learn more', 'Asks', 'Thanks and Asks',
        'Fundraising & Financing', 'Fundraising - Equity', 'Product and Technology', 'Key Events', 'Team & Culture',
        'Wrapped & Founders Reflection', 'Debt & Finance', 'Debt & Financing', '🏋 Challenges', 'Risks', 'Looking Ahead', '📈 KPIs',
        'Update on Fundraising / Lowlights and Focus Areas', 'Blurbs to facilitate connections you can help us with',
    ]
    highlight_section = extract_section_by_aliases(combined_text, SECTION_ALIASES['highlights'], stop_headings)
    looking_ahead_section = extract_section_by_aliases(
        combined_text,
        ['Looking Ahead'],
        ['Risks', 'Closing Thoughts', 'How you can help', 'Thanks and Asks']
    )
    highlight_items = (highlight_section or []) + (looking_ahead_section or [])
    highlights = _filter_section_items(highlight_items, 'highlights')
    asks = _filter_section_items(
        extract_section_by_aliases(
            combined_text,
            SECTION_ALIASES['asks'],
            ['Runway', 'Learn more', 'Blurbs to facilitate connections', 'Highlights', 'Risks', 'Closing Thoughts', 'AltScore Investor/Internal Update', 'Investor/Internal Update', 'Investor Update']
        ),
        'asks',
    )
    risks = _filter_section_items(extract_section_by_aliases(combined_text, SECTION_ALIASES['risks'], ['How you can help', 'Asks', 'Thanks and Asks', 'Highlights', 'Looking Ahead', '📈 KPIs', '2026 Overall Targets', 'Closing Thoughts']), 'risks')
    return {
        'gmail_message_id': raw.get('gmail_message_id'),
        'gmail_thread_id': raw.get('gmail_thread_id'),
        'company_name': canonicalize_company_name(raw.get('company_name_hint') or infer_company(subject, body_text)),
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
        'confidence_json': confidence,
        'source_path': raw.get('source_path'),
        'parser_version': 'v3',
    }
