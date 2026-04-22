from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .vehicles import canonicalize_company_name

# Default period dict when inference fails (keeps downstream shape stable).
_EMPTY_PERIOD: dict[str, Any] = {
    'report_period_label': None,
    'report_quarter': None,
    'report_year': None,
    'report_month': None,
}


def source_occurred_at_iso(raw: dict[str, Any]) -> str | None:
    """
    Original event time from the source payload (email Date / Fathom call time).
    Prefer normalized ISO from ingestion when present.
    """
    iso = raw.get('received_at_iso')
    if isinstance(iso, str) and iso.strip():
        return iso.strip()
    ra = raw.get('received_at')
    if ra is not None and str(ra).strip():
        return str(ra).strip()
    return None


def infer_source_type_for_update(raw: dict[str, Any]) -> str:
    """
    Coarse source label for UI: gmail, fathom, pdf, or mixed (email + PDF text).
    """
    st = str(raw.get('source_type') or '').strip().lower()
    if st == 'fathom_meeting':
        return 'fathom'
    has_pdf = bool(str(raw.get('attachment_text') or '').strip())
    body = str(raw.get('body_text') or '').strip()
    if has_pdf and body:
        return 'mixed'
    if has_pdf:
        return 'pdf'
    return 'gmail'


def clean_bullet_line(text: str) -> str:
    """Strip noise from a single highlight/ask/risk line."""
    if not text:
        return ""
    line = str(text).strip()
    line = re.sub(r"(?i)^subject:\s*", "", line).strip()
    line = re.sub(r"(?i)^re:\s*", "", line).strip()
    line = re.sub(r"^\[[\d.]+\]\s*", "", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def clean_bullet_list(items: list[str]) -> list[str]:
    out: list[str] = []
    for raw in items:
        cleaned = clean_bullet_line(raw)
        if not cleaned or len(cleaned) < 3:
            continue
        if cleaned not in out:
            out.append(cleaned)
    return out[:24]


def refine_summary_paragraph(text: str) -> str:
    """
    Turn body-derived text into a single readable paragraph: drop obvious
    headers, Subject:/Forwarded lines, and collapse whitespace.
    """
    if not text:
        return ""
    lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"(?i)^subject:\s*", line):
            line = re.sub(r"(?i)^subject:\s*", "", line).strip()
        if re.match(r"(?i)^forwarded message\s*$", line):
            continue
        if re.match(r"(?i)^(from|to|cc|date|sent):\s*", line) and len(line) < 120:
            continue
        if "Forwarded message" in line and len(line) < 40:
            continue
        lines.append(line)
    joined = " ".join(lines)
    joined = re.sub(r"\s+", " ", joined).strip()
    return joined[:2000]


def parse_stringified_json_list(value: Any) -> list[str] | None:
    """
    If value is a string that looks like a JSON array of strings, parse it.
    Used when downstream stored json.dumps(list) as text.
    """
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s.startswith("["):
        return None
    try:
        parsed = json.loads(s)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    return [str(x).strip() for x in parsed if str(x).strip()]


def _as_text(value: Any) -> str:
    """Coerce optional raw input to a string for safe regex/slicing."""
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return str(value)


def _safe_re_search(pattern: str, text: str, flags: int = 0):
    """re.search that never raises on bad patterns or inputs."""
    try:
        return re.search(pattern, text, flags)
    except re.error:
        return None
    except (TypeError, ValueError):
        return None


MONTH_PATTERN = r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'

MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


SECTION_ALIASES = {
    'highlights': [
        'Key updates', 'Highlights', 'Highlights & Product', 'Key Events', 'What did we DO last month?',
        'Investor Update – Q4', '🏆 Achievements', '📈 Traction', 'TLDR',
        'Executive summary', 'Business highlights', 'Quarter in review', 'Key metrics snapshot',
    ],
    'asks': ['How you can help', 'Asks', 'Thanks and Asks', '👍 How can you help?', '🙏 Asks', 'Blurbs to facilitate connections you can help us with'],
    'risks': ['Risks', 'The Bad', '🔴 The Bad: Strategic Consolidation', '🏋 Challenges', 'Update on Fundraising / Lowlights and Focus Areas'],
}


SECTION_START_HINTS = [
    'key updates', 'highlights', 'kpi', 'kpi’s', "kpi's", 'runway', 'debt & finance',
    'debt & financing', 'fundraising', 'operations', 'tech', 'peru monthly kpi',
    'mexico monthly kpi', 'leasy kpi', 'shippify', 'reliv', 'investor update – q4', 'investor update - q4',
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
    try:
        name = value.strip(' –-|:')
        name = re.sub(r'\bQ[1-4][-\s]?20?\d{2,4}\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
        name = re.sub(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
        name = re.sub(r'\bInvestor/Internal Update\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
        name = re.sub(r'\bInvestor Update\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
        name = re.sub(r'\bMonthly Update\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
        name = re.sub(r'\bBOD Update\b', '', name, flags=re.IGNORECASE).strip(' –-|:')
        name = re.sub(r'\[[^\]]+\]', '', name).strip(' –-|:')
        return name or None
    except (re.error, TypeError, ValueError):
        return value.strip() or None


def infer_company(subject: str | None, body_text: str | None) -> str | None:
    text = _as_text(subject)
    body_safe = _as_text(body_text)
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
        m = _safe_re_search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return _clean_company_name(m.group(1))
            except (IndexError, AttributeError):
                continue
    if body_safe:
        m = _safe_re_search(r'Subject:\s*([^:]+):\s*Q\d', body_safe, re.IGNORECASE)
        if m:
            try:
                return _clean_company_name(m.group(1))
            except (IndexError, AttributeError):
                pass
        m = _safe_re_search(r'From:\s+[^<]+<[^>]+@([a-z0-9-]+)\.', body_safe, re.IGNORECASE)
        if m:
            try:
                return _clean_company_name(m.group(1).replace('-', ' ').title().replace(' ', ''))
            except (IndexError, AttributeError):
                pass
    return None


def infer_period(subject: str | None, body_text: str | None) -> dict[str, Any]:
    subj_s = _as_text(subject)
    body_s = _as_text(body_text)
    body_clip = body_s[:4000] if body_s else ''
    text = ' '.join(part for part in (subj_s, body_clip) if part)
    quarter_match = _safe_re_search(r'\bQ([1-4])(?:[-\s]?(20\d{2}|\d{2}))\b', text, re.IGNORECASE)
    if quarter_match:
        try:
            q = int(quarter_match.group(1))
            y = quarter_match.group(2)
            if not y:
                raise ValueError('missing year')
            year = int(y) if len(y) == 4 else 2000 + int(y)
            return {
                'report_period_label': f'Q{q} {year}',
                'report_quarter': q,
                'report_year': year,
                'report_month': None,
            }
        except (ValueError, TypeError, IndexError, AttributeError):
            pass
    quarter_subject_match = _safe_re_search(r'\bQ([1-4])\b', subj_s, re.IGNORECASE)
    forward_date_match = _safe_re_search(
        r'Date:\s+\w+,\s+('
        r'January|February|March|April|May|June|July|August|September|October|November|December'
        r'|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{1,2},\s+(20\d{2})',
        body_s,
        re.IGNORECASE,
    )
    if quarter_subject_match and forward_date_match:
        try:
            q = int(quarter_subject_match.group(1))
            month_token = forward_date_match.group(1).lower()[:3]
            month_map = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
            year = int(forward_date_match.group(2))
            month_num = month_map.get(month_token)
            if month_num is None:
                pass
            else:
                if month_num <= 3:
                    year -= 1
                return {
                    'report_period_label': f'Q{q} {year}',
                    'report_quarter': q,
                    'report_year': year,
                    'report_month': None,
                }
        except (ValueError, TypeError, IndexError, AttributeError):
            pass
    try:
        range_match = re.search(rf'{MONTH_PATTERN}\s+\d{{1,2}}\s*[-–]\s+{MONTH_PATTERN}\s+\d{{1,2}}\s*(20\d{{2}})', text, re.IGNORECASE)
    except re.error:
        range_match = None
    if range_match:
        try:
            start_month = MONTHS.get(range_match.group(1).lower())
            end_month_name = range_match.group(2).lower()
            year = int(range_match.group(3))
            end_month = MONTHS.get(end_month_name)
            if start_month is None or end_month is None:
                pass
            else:
                quarter = (end_month - 1) // 3 + 1
                return {
                    'report_period_label': f'Q{quarter} {year}',
                    'report_quarter': quarter,
                    'report_year': year,
                    'report_month': None,
                }
        except (ValueError, TypeError, IndexError, AttributeError, KeyError):
            pass
    month_match = _safe_re_search(
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})',
        text,
        re.IGNORECASE,
    )
    if month_match:
        try:
            month_name = month_match.group(1).lower()
            month_num = MONTHS.get(month_name)
            year = int(month_match.group(2))
            if month_num is None:
                pass
            else:
                return {
                    'report_period_label': f'{month_match.group(1)} {year}',
                    'report_quarter': None,
                    'report_year': year,
                    'report_month': month_num,
                }
        except (ValueError, TypeError, IndexError, AttributeError):
            pass
    return dict(_EMPTY_PERIOD)


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
    try:
        value = _as_text(text)
        value = value.replace('\r\n', '\n').replace('\r', '\n')
        value = value.replace('\u202f', ' ').replace('\xa0', ' ')
        value = value.replace('–', '-').replace('—', '-')
        value = value.replace('“', '"').replace('”', '"').replace('’', "'")
        value = re.sub(r'\*+', '', value)
        value = re.sub(r'[ \t]+', ' ', value)
        value = re.sub(r'\n{3,}', '\n\n', value)
        return value.strip()
    except (re.error, TypeError, ValueError):
        return _as_text(text).strip()


def _cleanup_section_text(text: str) -> str:
    try:
        value = _normalize_text(text)
    except Exception:
        return ''
    try:
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
        value = re.sub(r'^\s*FATHOM MEETING RECORDING\s*$', '', value, flags=re.MULTILINE | re.IGNORECASE)
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
    except re.error:
        return _normalize_text(text)


def _strip_signature(text: str) -> str:
    try:
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
    except (re.error, TypeError, ValueError):
        return _as_text(text)


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
        try:
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
        except (ValueError, TypeError, AttributeError, re.error):
            continue

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
        m = _safe_re_search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        try:
            built = builder(m)
            _set_metric(metrics, confidence, name, built, _line_snippet(text, m.start(), m.end()), score, origin)
        except (ValueError, TypeError, AttributeError, IndexError, ZeroDivisionError):
            continue

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
        try:
            m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        except re.error:
            continue
        if not m:
            continue
        try:
            built = builder(m)
            _set_metric(metrics, confidence, name, built, _line_snippet(text, m.start(), m.end()), score, origin)
        except (ValueError, TypeError, AttributeError, IndexError, ZeroDivisionError):
            continue

    try:
        yoy_matches = re.findall(r'(\d+(?:\.\d+)?)%\s+YoY', text, re.IGNORECASE)
    except re.error:
        yoy_matches = []
    if yoy_matches and 'yoy_percentages' not in metrics:
        try:
            metrics['yoy_percentages'] = [float(x) for x in yoy_matches]
            snippet_bits = re.findall(r'.{0,60}\d+(?:\.\d+)?%\s+YoY.{0,60}', text, re.IGNORECASE)[:2]
            confidence['yoy_percentages'] = {
                'score': CONFIDENCE_LOW,
                'origin': 'narrative_growth',
                'source_snippet': ' '.join(snippet_bits)[:400],
            }
        except (ValueError, TypeError):
            pass

    return metrics, confidence


def _section_text(body_text: str | None, heading: str, stop_headings: list[str] | None = None, window: int = 5000) -> str:
    try:
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
    except (TypeError, ValueError, AttributeError):
        return ''


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
        try:
            is_label_line = bool(re.match(r'^[A-Z][a-z]+:', line))
        except re.error:
            is_label_line = False
        if len(line) > 40 and not is_label_line:
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
        try:
            bullets = re.findall(r'\n\s*[-•]\s*(.+)', section)
        except re.error:
            bullets = []
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
    raw = ' '.join(useful)[:1200]
    return refine_summary_paragraph(raw)[:1200]


def _text_for_summary(raw: dict[str, Any], combined_text: str) -> str:
    """Fathom updates: weight the API summary over raw transcript for the short summary field."""
    if raw.get('source_type') != 'fathom_meeting':
        return combined_text
    m = _safe_re_search(
        r'---\s*SUMMARY\s*---\s*(.*?)(?=---\s*TRANSCRIPT\s*---|\Z)',
        combined_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return combined_text
    block = (m.group(1) or '').strip()
    if len(block) < 40:
        return combined_text
    tail = ''
    tm = _safe_re_search(r'---\s*TRANSCRIPT\s*---\s*(.*)\Z', combined_text, re.DOTALL | re.IGNORECASE)
    if tm:
        tail = (tm.group(1) or '').strip()[:1200]
    return f'{block}\n\n{tail}'.strip() if tail else block


def _cap_metrics_by_confidence(
    metrics: dict[str, Any],
    confidence: dict[str, Any],
    max_metrics: int = 18,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(metrics) <= max_metrics:
        return metrics, confidence
    scored: list[tuple[float, str]] = []
    for key in metrics:
        sc = float((confidence.get(key) or {}).get('score') or 0.5)
        scored.append((sc, key))
    scored.sort(key=lambda x: (-x[0], x[1]))
    keep = {k for _, k in scored[:max_metrics]}
    new_m = {k: metrics[k] for k in metrics if k in keep}
    new_c = {k: confidence[k] for k in confidence if k in keep}
    return new_m, new_c


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
    try:
        period = infer_period(subject, combined_text)
    except Exception:
        period = dict(_EMPTY_PERIOD)
    try:
        metrics, confidence = extract_metrics(combined_text)
    except Exception:
        metrics, confidence = {}, {}
    metrics, confidence = _cap_metrics_by_confidence(metrics, confidence, max_metrics=18)
    stop_headings = [
        'How you can help', 'Runway', 'Learn more', 'Asks', 'Thanks and Asks',
        'Fundraising & Financing', 'Fundraising - Equity', 'Product and Technology', 'Key Events', 'Team & Culture',
        'Wrapped & Founders Reflection', 'Debt & Finance', 'Debt & Financing', '🏋 Challenges', 'Risks', 'Looking Ahead', '📈 KPIs',
        'Update on Fundraising / Lowlights and Focus Areas', 'Blurbs to facilitate connections you can help us with',
        'Executive summary', 'Business highlights',
    ]
    try:
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
    except Exception:
        highlights, asks, risks = [], [], []
    highlights = clean_bullet_list(highlights)
    asks = clean_bullet_list(asks)
    risks = clean_bullet_list(risks)
    try:
        inferred_company = infer_company(subject, body_text)
        company_resolved = canonicalize_company_name(raw.get('company_name_hint') or inferred_company)
    except Exception:
        try:
            hint = raw.get('company_name_hint')
            company_resolved = canonicalize_company_name(hint) if hint else None
        except Exception:
            company_resolved = None
    return {
        'gmail_message_id': raw.get('gmail_message_id'),
        'gmail_thread_id': raw.get('gmail_thread_id'),
        'company_name': company_resolved,
        'subject': subject,
        'from_address': raw.get('from_address'),
        'to_addresses': raw.get('to_addresses', []),
        'received_at': raw.get('received_at'),
        **period,
        'summary': summarize(_text_for_summary(raw, combined_text)),
        'metrics_json': metrics,
        'highlights_json': highlights,
        'asks_json': asks,
        'risks_json': risks,
        'people_json': [],
        'confidence_json': confidence,
        'source_path': raw.get('source_path'),
        'parser_version': 'v3',
        'source_occurred_at': source_occurred_at_iso(raw),
        'source_type': infer_source_type_for_update(raw),
    }
