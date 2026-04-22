"""
Generate fund-level Quarterly LP report narratives from StartupUpdate rows.
"""

from __future__ import annotations

import json
import re
from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dashboard.models import QuarterlyLPReport, StartupUpdate


SYSTEM_PROMPT = """You are an expert Venture Capital General Partner writing a quarterly LP (Limited Partner) report.
You will be provided with a list of individual startup updates for a specific investment vehicle (either a multi-asset Fund or a single-asset SPV) for a specific quarter.

Your task is to synthesize these individual updates into a cohesive, professional, and objective investor-facing narrative.

IF THE INPUT CONTAINS MULTIPLE STARTUPS (Fund Report):
Return a JSON object with two keys:
1. "summary_of_progress": A 2-3 paragraph macro-level summary of how the portfolio performed this quarter. Highlight major themes (e.g., "Fund performance remained stable...", "Several companies surpassed $1M ARR..."). Mention 1-2 standout companies by name if they had massive wins or acquisitions.
2. "significant_developments": A markdown-formatted string grouping specific notable startup updates into categories like "Fundraising:" and "Growth:". (e.g., "• **Company X** reached $500K ARR (+36% QoQ)...").

IF THE INPUT CONTAINS ONLY ONE STARTUP (SPV Report):
Return a JSON object with two keys:
1. "summary_of_progress": A 2-3 paragraph summary of the startup's "Current Opportunities & Challenges" for the quarter based on the provided update.
2. "significant_developments": A short markdown string detailing any "Fundraising Updates" or major shifts in runway/burn rate.

Tone Guidelines:
- Professional, concise, and financially literate.
- Do not use filler words or marketing fluff.
- If data is missing, do not invent it.
- Focus on capital efficiency, ARR/Revenue growth, milestones, and runway."""


def _parse_period_label(period_label: str) -> tuple[str, int]:
    m = re.search(r"\bQ([1-4])\s+(\d{4})\b", period_label, flags=re.IGNORECASE)
    if m:
        return f"Q{int(m.group(1))}", int(m.group(2))
    return "Q0", 0


def _format_startup_update_block(update) -> str:
    startup_name = update.startup.name if getattr(update, "startup", None) else "Unknown Startup"
    metrics = list(update.metrics.all())
    metric_lines = [f"- {m.name}: {m.value}" for m in metrics if (m.name or "").strip() and (m.value or "").strip()]
    highlights = str(update.highlights or "").strip()
    asks = str(update.asks or "").strip()
    risks = str(update.risks or "").strip()
    summary = str(update.opportunities_and_challenges or "").strip()
    return "\n".join(
        [
            f"Company: {startup_name}",
            f"Summary: {summary or '(none)'}",
            "Metrics:",
            "\n".join(metric_lines) if metric_lines else "- (none)",
            f"Highlights: {highlights or '(none)'}",
            f"Risks: {risks or '(none)'}",
            f"Asks: {asks or '(none)'}",
        ]
    )


def _build_user_prompt(vehicle_name: str, period_label: str, updates: list[Any]) -> str:
    blocks = []
    for idx, update in enumerate(updates, start=1):
        blocks.append(f"--- STARTUP UPDATE {idx} ---\n{_format_startup_update_block(update)}")
    return (
        f"Vehicle: {vehicle_name}\n"
        f"Report period: {period_label}\n"
        f"Startup update count: {len(updates)}\n\n"
        "Return only valid JSON with keys summary_of_progress and significant_developments.\n\n"
        + "\n\n".join(blocks)
    )


def _parse_json_response(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    parsed = json.loads(text or "{}")
    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object")
    return parsed


def generate_quarterly_lp_report(
    vehicle_id: int, period_label: str, openai_api_key: str
) -> tuple["QuarterlyLPReport", list["StartupUpdate"]]:
    """
    Generate or update a QuarterlyLPReport from StartupUpdate rows.

    Returns:
        tuple[QuarterlyLPReport, list[StartupUpdate]]
    """
    from dashboard.models import QuarterlyLPReport, StartupUpdate, Vehicle
    from openai import OpenAI

    vehicle = Vehicle.objects.get(pk=vehicle_id)
    quarter, year = _parse_period_label(period_label)
    updates = list(
        StartupUpdate.objects.filter(vehicle_id=vehicle_id, period_label=period_label)
        .select_related("startup")
        .prefetch_related("metrics")
        .order_by("startup__name", "id")
    )
    if not updates and year > 0:
        updates = list(
            StartupUpdate.objects.filter(vehicle_id=vehicle_id, quarter=quarter, year=year)
            .select_related("startup")
            .prefetch_related("metrics")
            .order_by("startup__name", "id")
        )
    if not updates:
        raise ValueError(f"No StartupUpdate rows found for vehicle={vehicle_id} period={period_label!r}")

    client = OpenAI(api_key=openai_api_key)
    completion = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(vehicle.name, period_label, updates)},
        ],
    )
    raw_content = completion.choices[0].message.content or "{}"
    payload = _parse_json_response(raw_content)

    report, _ = QuarterlyLPReport.objects.get_or_create(
        vehicle=vehicle,
        quarter=quarter,
        year=year,
        defaults={"report_period_label": period_label},
    )
    report.report_period_label = period_label
    report.summary_of_progress = str(payload.get("summary_of_progress") or "").strip()
    report.significant_developments = str(payload.get("significant_developments") or "").strip()
    report.status = "Draft"
    report.save()

    return report, updates
