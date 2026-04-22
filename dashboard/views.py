import ast
import json
import sys
from pathlib import Path

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from .models import QuarterlyLPReport, Startup, StartupUpdate, Vehicle

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


_SOURCE_TYPE_LABELS = {
    'gmail': 'Gmail',
    'fathom': 'Fathom',
    'pdf': 'PDF',
    'mixed': 'Mixed',
}


def _source_type_label(code: str | None) -> str | None:
    if not code:
        return None
    return _SOURCE_TYPE_LABELS.get(str(code).lower(), str(code))


def _dt_iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value) if value else None


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
        'source_type',
        'source_occurred_at',
        'ingestion_ran_at',
    )
    payload = [
        {
            'id': report['id'],
            'period_label': report['period_label'],
            'quarter': report['quarter'],
            'year': report['year'],
            'received_at': report['received_at'].isoformat() if report['received_at'] else None,
            'source_type': report['source_type'],
            'source_label': _source_type_label(report['source_type']),
            'source_occurred_at': report['source_occurred_at'].isoformat() if report['source_occurred_at'] else None,
            'ingestion_ran_at': report['ingestion_ran_at'].isoformat() if report['ingestion_ran_at'] else None,
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
        'source_type': report.source_type,
        'source_label': _source_type_label(report.source_type),
        'source_occurred_at': _dt_iso(report.source_occurred_at),
        'ingestion_ran_at': _dt_iso(report.ingestion_ran_at),
        'summary': _clean_narrative_block(report.opportunities_and_challenges),
        'opportunities_and_challenges': _clean_narrative_block(report.opportunities_and_challenges),
        'fundraising_updates': _clean_narrative_block(report.fundraising_updates),
        'highlights_json': _section_field_to_list(report.highlights),
        'asks_json': _section_field_to_list(report.asks),
        'risks_json': _section_field_to_list(report.risks),
        # Backward-compatible aliases for existing frontend consumers.
        'highlights': _section_field_to_list(report.highlights),
        'asks': _section_field_to_list(report.asks),
        'risks': _section_field_to_list(report.risks),
        'people': report.people,
        'metrics': metrics,
    }
    return JsonResponse(payload)


@require_http_methods(["POST"])
def api_generate_vehicle_report(request, id):
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid JSON body"}, status=400)
    period_label = str(body.get("period_label") or "").strip()
    if not period_label:
        return JsonResponse({"detail": "period_label is required"}, status=400)

    # Defer import to keep dashboard startup light when API key isn't needed.
    from lpupdate.extraction.lp_report_generator import generate_quarterly_lp_report
    from lpupdate.config import Settings

    settings = Settings.from_env()
    if not settings.openai_api_key:
        return JsonResponse({"detail": "OPENAI_API_KEY is not set"}, status=400)
    try:
        report, updates = generate_quarterly_lp_report(
            vehicle_id=id,
            period_label=period_label,
            openai_api_key=settings.openai_api_key,
        )
    except Vehicle.DoesNotExist:
        return JsonResponse({"detail": "Vehicle not found"}, status=404)
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"detail": f"Report generation failed: {exc}"}, status=500)

    return JsonResponse(
        {
            "report_id": report.id,
            "vehicle_id": report.vehicle_id,
            "report_period_label": report.report_period_label,
            "status": report.status,
            "summary_of_progress": report.summary_of_progress,
            "significant_developments": report.significant_developments,
            "startup_updates": [
                {
                    "id": u.id,
                    "startup_name": u.startup.name if u.startup else None,
                    "period_label": u.period_label,
                    "summary": u.opportunities_and_challenges,
                    "highlights": _section_field_to_list(u.highlights),
                    "risks": _section_field_to_list(u.risks),
                    "asks": _section_field_to_list(u.asks),
                }
                for u in updates
            ],
        }
    )


@require_http_methods(["GET"])
def api_lp_reports(request):
    report_id_raw = request.GET.get("id")
    if report_id_raw:
        try:
            report = QuarterlyLPReport.objects.select_related("vehicle").get(pk=int(report_id_raw))
        except (ValueError, QuarterlyLPReport.DoesNotExist):
            return JsonResponse({"detail": "Not found."}, status=404)
        updates = list(
            StartupUpdate.objects.filter(
                vehicle_id=report.vehicle_id,
                period_label=report.report_period_label,
            )
            .select_related("startup")
            .order_by("startup__name", "id")
            .values("id", "startup__name", "period_label", "opportunities_and_challenges", "highlights", "risks", "asks")
        )
        payload = {
            "id": report.id,
            "vehicle_id": report.vehicle_id,
            "vehicle_name": report.vehicle.name if report.vehicle_id else None,
            "report_period_label": report.report_period_label,
            "status": report.status,
            "summary_of_progress": report.summary_of_progress,
            "significant_developments": report.significant_developments,
            "startup_updates": [
                {
                    "id": u["id"],
                    "startup_name": u["startup__name"],
                    "period_label": u["period_label"],
                    "summary": u["opportunities_and_challenges"],
                    "highlights": _section_field_to_list(u["highlights"]),
                    "risks": _section_field_to_list(u["risks"]),
                    "asks": _section_field_to_list(u["asks"]),
                }
                for u in updates
            ],
        }
        return JsonResponse(payload)

    rows = QuarterlyLPReport.objects.select_related("vehicle").order_by("-year", "-quarter", "-id")
    payload = [
        {
            "id": r.id,
            "vehicle_id": r.vehicle_id,
            "vehicle_name": r.vehicle.name if r.vehicle_id else None,
            "report_period_label": r.report_period_label or f"{r.quarter} {r.year}",
            "status": r.status,
            "summary_of_progress": (r.summary_of_progress or "")[:240],
        }
        for r in rows
    ]
    return JsonResponse(payload, safe=False)


@require_http_methods(["POST"])
def api_lp_report_update(request, id):
    try:
        report = QuarterlyLPReport.objects.get(pk=id)
    except QuarterlyLPReport.DoesNotExist:
        return JsonResponse({"detail": "Not found."}, status=404)
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Invalid JSON body"}, status=400)

    if "summary_of_progress" in body:
        report.summary_of_progress = str(body.get("summary_of_progress") or "")
    if "significant_developments" in body:
        report.significant_developments = str(body.get("significant_developments") or "")
    if "status" in body:
        status = str(body.get("status") or "").strip()
        if status in {"Draft", "Published"}:
            report.status = status
    report.save()
    return JsonResponse(
        {
            "id": report.id,
            "status": report.status,
            "summary_of_progress": report.summary_of_progress,
            "significant_developments": report.significant_developments,
        }
    )
