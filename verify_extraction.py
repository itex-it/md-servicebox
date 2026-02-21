import requests
import time
import json

BASE_URL = "http://localhost:8005"
API_KEY = "SECRET_TOKEN_123"
HEADERS = {"X-Auth-Token": API_KEY}
VIN = "VF3EBRHD8BZ038648"

print(f"1. Triggering full extraction for VIN: {VIN}")
payload = {
    "vin": VIN,
    "force_refresh": True, # Force new download to trigger the parsing logic
    "priority": True
}
res = requests.post(f"{BASE_URL}/api/maintenance-plan", json=payload, headers=HEADERS)
res_data = res.json()
print("Trigger Response:")
print(json.dumps(res_data, indent=2))

job_id = res_data.get("job_id")
if not job_id:
    print("Failed to get job ID. Exiting.")
    exit(1)

print("\n2. Polling for job completion...")
while True:
    j_res = requests.get(f"{BASE_URL}/api/jobs/{job_id}", headers=HEADERS)
    j_data = j_res.json()
    status = j_data.get("status")
    print(f"Status: {status}...")
    
    if status == "success":
        print(f"Job completed successfully!")
        break
    elif status == "error":
        print(f"Job failed: {j_data.get('error_message')}")
        exit(1)
        
    time.sleep(3)

print("\n3. Testing /api/vehicle/{vin}/services (Standard conditions)")
res_std = requests.get(f"{BASE_URL}/api/vehicle/{VIN}/services?severe_conditions=false", headers=HEADERS)
print("Response Standard:")
print(json.dumps(res_std.json(), indent=2))

print("\n4. Testing /api/vehicle/{vin}/services (Severe conditions)")
res_sev = requests.get(f"{BASE_URL}/api/vehicle/{VIN}/services?severe_conditions=true", headers=HEADERS)
print("Response Severe:")
print(json.dumps(res_sev.json(), indent=2))

print("\n5. Testing /api/maintenance-plan (Cached with severe flag)")
payload_cached = {
    "vin": VIN,
    "force_refresh": False,
    "severe_conditions": True
}
res_cached = requests.post(f"{BASE_URL}/api/maintenance-plan", json=payload_cached, headers=HEADERS)
print("Cached Response with Severe Services:")
print(json.dumps(res_cached.json().get("services", []), indent=2))
