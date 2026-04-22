import os
import sys
from pathlib import Path
import django
import json
# System/driver: psycopg2 (e.g. apt python3-psycopg2), not pip psycopg v3.
import psycopg2

# Allow direct execution via `python scripts/migrate_data.py` from repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from dashboard.models import Firm, Vehicle, Startup, VehicleStartup, StartupUpdate, StartupMetric
from lpupdate.metrics_display import format_metric_value_for_display

def run_migration():
    print("Starting migration...")
    firm, _ = Firm.objects.get_or_create(name="BuenTrip Ventures Capital Management, LLC")
    print(f"Firm: {firm.name}")

    # Connect to the database directly to read old tables (raw SQL, not Django ORM)
    # We do this because Django models don't map to the old tables
    db_url = os.environ.get('LPUPDATE_DATABASE_URL')
    if not db_url:
        print("Missing LPUPDATE_DATABASE_URL")
        return

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, canonical_name, vehicles_json FROM companies;")
            companies_data = cur.fetchall()

            company_map = {}
            for row in companies_data:
                old_id, name, vehicles_json = row
                startup, _ = Startup.objects.get_or_create(name=name)
                company_map[old_id] = startup
                
                if vehicles_json:
                    # jsonb may come back as dict/list or str depending on adapter
                    if isinstance(vehicles_json, str):
                        try:
                            vehicles_json = json.loads(vehicles_json)
                        except:
                            vehicles_json = []
                            
                    for v_name in vehicles_json:
                        vehicle, _ = Vehicle.objects.get_or_create(name=v_name, firm=firm)
                        VehicleStartup.objects.get_or_create(vehicle=vehicle, startup=startup)

            print(f"Migrated {len(company_map)} startups.")

            cur.execute(
                """
                SELECT id, company_id, report_period_label, report_quarter, report_year, summary,
                       metrics_json, highlights_json, asks_json, received_at,
                       source_occurred_at, ingestion_ran_at, source_type
                FROM quarterly_updates;
                """
            )
            updates_data = cur.fetchall()

            reports_created = 0
            metrics_created = 0

            for row in updates_data:
                (
                    old_id,
                    company_id,
                    label,
                    quarter,
                    year,
                    summary,
                    metrics_json,
                    highlights_json,
                    asks_json,
                    received_at,
                    source_occurred_at,
                    ingestion_ran_at,
                    source_type,
                ) = row
                
                if not company_id:
                    continue
                    
                startup = company_map.get(company_id)
                if not startup:
                    continue
                    
                if not quarter or str(quarter).startswith("U-"):
                    if received_at:
                        year = received_at.year
                        quarter = f"Q{(received_at.month - 1) // 3 + 1}"
                    else:
                        quarter = "NA"
                        year = 0
                elif not year:
                    year = 0
                    
                if isinstance(metrics_json, str):
                    try:
                        metrics_json = json.loads(metrics_json)
                    except:
                        metrics_json = {}
                        
                if not metrics_json:
                    metrics_json = {}

                # A startup might be in multiple vehicles, so we duplicate the report for each vehicle
                # (or just the first one if we want to be simple, but usually it belongs to the vehicle)
                vehicle_startups = VehicleStartup.objects.filter(startup=startup)
                if not vehicle_startups.exists():
                    continue
                    
                for vs in vehicle_startups:
                    report, created = StartupUpdate.objects.get_or_create(
                        vehicle=vs.vehicle,
                        startup=startup,
                        quarter=str(quarter)[:10],
                        year=year,
                        defaults={
                            'opportunities_and_challenges': summary,
                            'highlights': json.dumps(highlights_json) if highlights_json else '',
                            'asks': json.dumps(asks_json) if asks_json else '',
                            'period_label': label,
                            'received_at': received_at,
                            'source_type': source_type,
                            'source_occurred_at': source_occurred_at,
                            'ingestion_ran_at': ingestion_ran_at,
                        }
                    )
                    
                    if not created:
                        report.opportunities_and_challenges = summary
                        report.highlights = json.dumps(highlights_json) if highlights_json else ''
                        report.asks = json.dumps(asks_json) if asks_json else ''
                        report.period_label = label
                        if received_at:
                            report.received_at = received_at
                        if source_type:
                            report.source_type = source_type
                        if source_occurred_at:
                            report.source_occurred_at = source_occurred_at
                        if ingestion_ran_at:
                            report.ingestion_ran_at = ingestion_ran_at
                        report.save()
                    
                    if created:
                        reports_created += 1
                        for k, v in metrics_json.items():
                            StartupMetric.objects.create(
                                update=report,
                                name=str(k)[:255],
                                value=format_metric_value_for_display(v),
                            )
                            metrics_created += 1

            print(f"Migrated {reports_created} reports and {metrics_created} metrics.")

if __name__ == '__main__':
    run_migration()
