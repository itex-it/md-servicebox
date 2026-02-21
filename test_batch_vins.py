import requests
import json
import time

vins = [
    "VF3MCYHZRLL006667",
    "VF3MCYHZRKS496649",
    "VR7ECYHZRLJ561266",
    "VR7CCHPV4ST050208",
    "VR1J45GBUKY179922",
    "VF7VFEHTMPZ044822"
]

url = "http://localhost:8005/api/maintenance-plan"
headers = {
    "X-Auth-Token": "SECRET_TOKEN_123",
    "Content-Type": "application/json"
}

print(f"Starting batch test for {len(vins)} VINs...")

for vin in vins:
    print(f"\nProcessing VIN: {vin}")
    data = {"vin": vin}
    try:
        start = time.time()
        response = requests.post(url, headers=headers, json=data, timeout=300)
        duration = time.time() - start
        
        if response.status_code == 200:
            res_json = response.json()
            recalls = res_json.get('vehicle_data', {}).get('recalls', {})
            print(f"  Success ({duration:.1f}s)")
            print(f"  Recall Status: {recalls.get('status')}")
            print(f"  Message: {recalls.get('message')}")
            if 'details' in recalls:
                print("  Details:")
                for d in recalls['details']:
                    print(f"    - {d['code']}: {d['status']} ({d['description']})")
            else:
                print("  No details found.")
        else:
            print(f"  Failed (Status {response.status_code}): {response.text}")
            
    except Exception as e:
        print(f"  Error: {e}")
        
    print("-" * 40)
