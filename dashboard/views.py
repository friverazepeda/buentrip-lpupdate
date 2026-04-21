import ast
import json
import sys
from pathlib import Path

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify

from .models import Startup, StartupUpdate, Vehicle

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

try:
    from lpupdate.metrics_display import format_metric_value_for_display
    from lpupdate.parse_updates import refine_summary_paragraph
except ImportError:
    def format_metric_value_for_display(value, *, max_len=255):
        return str(value)[:max_len] if value is not None else ""

    def refine_summary_paragraph(text):
        return (text or "").strip()[:2000]


def _section_field_to_list(value):
    """TextField may store json.dumps(list) or newline-separated bullets; API returns a real JSON array."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()]
    s = str(value).strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except (ValueError, SyntaxError):
                pass
    return [line.strip() for line in s.splitlines() if line.strip()]


def _format_metric_cell(value: str | None) -> str:
    """Turn repr/JSON metric values into display strings (matches parser metrics_display)."""
    if value is None:
        return ""
    v = str(value).strip()
    if not v:
        return ""
    if v.startswith("{") or (v.startswith("[") and v.endswith("]")):
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(v)
            except (ValueError, SyntaxError):
                return v
        return format_metric_value_for_display(parsed)
    return v


def _clean_narrative_block(text: str | None) -> str | None:
    if not text or not str(text).strip():
        return None
    raw = str(text).strip()
    refined = refine_summary_paragraph(raw)
    return refined if refined else raw

def index(request):
    startups = Startup.objects.all().order_by('name')
    vehicles = Vehicle.objects.all().order_by('name')
    return render(request, 'dashboard/index.html', {'startups': startups, 'vehicles': vehicles})

def startup_detail(request, pk):
    startup = get_object_or_404(Startup, pk=pk)
    reports = StartupUpdate.objects.filter(startup=startup).order_by('-year', '-quarter')
    return render(request, 'dashboard/startup_detail.html', {'startup': startup, 'reports': reports})

def report_detail(request, pk):
    report = get_object_or_404(StartupUpdate, pk=pk)
    return render(request, 'dashboard/report_detail.html', {'report': report})


def api_startups(request):
    startups = Startup.objects.all().order_by('name').values('id', 'name')
    payload = [
        {
            'id': row['id'],
            'name': row['name'],
            'slug': slugify(row['name']),
        }
        for row in startups
    ]
    return JsonResponse(payload, safe=False)


def api_startup_by_slug(request, slug):
    for row in Startup.objects.all().order_by('name').values('id', 'name'):
        if slugify(row['name']) == slug:
            return JsonResponse(
                {
                    'id': row['id'],
                    'name': row['name'],
                    'slug': slugify(row['name']),
                }
            )
    return JsonResponse({'detail': 'Not found.'}, status=404)


def api_startup_reports_by_slug(request, slug):
    startup_row = None
    for row in Startup.objects.all().order_by('name').values('id', 'name'):
        if slugify(row['name']) == slug:
            startup_row = row
            break

    if startup_row is None:
        return JsonResponse({'detail': 'Not found.'}, status=404)

    reports = StartupUpdate.objects.filter(startup_id=startup_row['id']).order_by('-year', '-quarter').values(
        'id',
        'period_label',
        'quarter',
        'year',
        'received_at',
    )
    payload = [
        {
            'id': report['id'],
            'period_label': report['period_label'],
            'quarter': report['quarter'],
            'year': report['year'],
            'received_at': report['received_at'].isoformat() if report['received_at'] else None,
        }
        for report in reports
    ]
    return JsonResponse(payload, safe=False)


def api_report_by_id(request, id):
    try:
        report = StartupUpdate.objects.select_related('startup', 'vehicle').get(pk=id)
    except StartupUpdate.DoesNotExist:
        return JsonResponse({'detail': 'Not found.'}, status=404)

    metrics = [
        {
            'name': metric.name,
            'value': _format_metric_cell(metric.value),
            'change': metric.change,
        }
        for metric in report.metrics.all()
    ]

    payload = {
        'id': report.id,
        'startup_id': report.startup_id,
        'startup_name': report.startup.name if report.startup else None,
        'vehicle_id': report.vehicle_id,
        'vehicle_name': report.vehicle.name,
        'period_label': report.period_label,
        'quarter': report.quarter,
        'year': report.year,
        'received_at': report.received_at.isoformat() if report.received_at else None,
        'opportunities_and_challenges': _clean_narrative_block(report.opportunities_and_challenges),
        'fundraising_updates': _clean_narrative_block(report.fundraising_updates),
        'highlights': _section_field_to_list(report.highlights),
        'risks': _section_field_to_list(report.risks),
        'asks': _section_field_to_list(report.asks),
        'people': report.people,
        'metrics': metrics,
    }
    return JsonResponse(payload)
