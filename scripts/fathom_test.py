import os
import json
import urllib.request
from lpupdate.config import load_dotenv, Settings

load_dotenv()
FATHOM_API_KEY = os.getenv('FATHOM_API_KEY')
if not FATHOM_API_KEY:
    print("Please set FATHOM_API_KEY in .env")
    exit(1)

req = urllib.request.Request(
    'https://api.fathom.ai/external/v1/recordings?limit=5',
    headers={'Authorization': f'Bearer {FATHOM_API_KEY}'}
)
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode())
