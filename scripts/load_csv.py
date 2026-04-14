import os
import django
import csv

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
django.setup()

from dashboard.models import Startup, Vehicle, VehicleStartup

def load_csv():
    csv_path = '/home/frivera/.openclaw/media/inbound/Startup-Portfolio_Companies_LPUpdate_2---288542d6-3636-415b-88fb-4bf7399798bb.csv'
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            print("Row dict keys:", row.keys())
            name = row.get('Legal Name', '').strip()
            print(f"Reading row: {name}")
            if not name:
                # try the first key just in case of BOM or whitespace
                first_key = list(row.keys())[0]
                name = row.get(first_key, '').strip()
                if not name:
                    continue
                
            startup, created = Startup.objects.get_or_create(name=name)
            
            startup.description = row.get('One Liner', '').strip()
            startup.sector = row.get('Sectors/Vertical', '').strip()
            startup.business_model = row.get('Business Model', '').strip()
            startup.sub_segment_niche = row.get('Sug-segment/Niche', '').strip()
            
            startup.save()
            print(f"Updated {name}")
            
            # Link to Vehicle
            vehicle_name = row.get('Portfolio Location', '').strip()
            if vehicle_name:
                vehicle_qs = Vehicle.objects.filter(name__icontains=vehicle_name)
                if vehicle_qs.exists():
                    vehicle = vehicle_qs.first()
                    VehicleStartup.objects.get_or_create(vehicle=vehicle, startup=startup)
                    print(f"  Linked to {vehicle.name}")
                else:
                    print(f"  Could not find vehicle matching: {vehicle_name}")

if __name__ == '__main__':
    load_csv()