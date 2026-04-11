import os
import django
import json
import psycopg

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
django.setup()

from dashboard.models import Firm, Vehicle, Startup, VehicleStartup, StartupUpdate, StartupMetric

def run_migration():
    print("Starting migration...")
    firm, _ = Firm.objects.get_or_create(name="BuenTrip Ventures Capital Management, LLC")
    print(f"Firm: {firm.name}")

    # Connect to the database directly to read old tables using psycopg
    # We do this because Django models don't map to the old tables
    db_url = os.environ.get('LPUPDATE_DATABASE_URL')
    if not db_url:
        print("Missing LPUPDATE_DATABASE_URL")
        return

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, canonical_name, vehicles_json FROM companies;")
            companies_data = cur.fetchall()

            company_map = {}
            for row in companies_data:
                old_id, name, vehicles_json = row
                startup, _ = Startup.objects.get_or_create(name=name)
                company_map[old_id] = startup
                
                if vehicles_json:
                    # Depending on psycopg version, jsonb might be dict/list already
                    if isinstance(vehicles_json, str):
                        try:
                            vehicles_json = json.loads(vehicles_json)
                        except:
                            vehicles_json = []
                            
                    for v_name in vehicles_json:
                        vehicle, _ = Vehicle.objects.get_or_create(name=v_name, firm=firm)
                        VehicleStartup.objects.get_or_create(vehicle=vehicle, startup=startup)

            print(f"Migrated {len(company_map)} startups.")

            cur.execute("SELECT id, company_id, report_period_label, report_quarter, report_year, summary, metrics_json, highlights_json, asks_json FROM quarterly_updates;")
            updates_data = cur.fetchall()

            reports_created = 0
            metrics_created = 0

            for row in updates_data:
                old_id, company_id, label, quarter, year, summary, metrics_json, highlights_json, asks_json = row
                
                if not company_id:
                    continue
                    
                startup = company_map.get(company_id)
                if not startup:
                    continue
                    
                if not quarter:
                    quarter = "Q?"
                if not year:
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
                        }
                    )
                    
                    if not created:
                        report.opportunities_and_challenges = summary
                        report.highlights = json.dumps(highlights_json) if highlights_json else ''
                        report.asks = json.dumps(asks_json) if asks_json else ''
                        report.period_label = label
                        report.save()
                    
                    if created:
                        reports_created += 1
                        for k, v in metrics_json.items():
                            StartupMetric.objects.create(
                                update=report,
                                name=str(k)[:255],
                                value=str(v)[:255]
                            )
                            metrics_created += 1

            print(f"Migrated {reports_created} reports and {metrics_created} metrics.")

if __name__ == '__main__':
    run_migration()
