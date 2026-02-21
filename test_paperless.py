import requests
import time
import json

BASE_URL = "http://127.0.0.1:8005"
API_KEY = "SECRET_TOKEN_123"
HEADERS = {"X-Auth-Token": API_KEY}
VIN = "VF3EBRHD8BZ038648"

print("1. Triggering full extraction for VIN (forcing new job):")
payload = {
    "vin": VIN,
    "force_refresh": True,
    "priority": True
}
res = requests.post(f"{BASE_URL}/api/maintenance-plan", json=payload, headers=HEADERS)
res_data = res.json()
print("Trigger Response:", res_data)

job_id = res_data.get("job_id")
if not job_id:
    exit(1)

print("\n2. Polling for job completion...")
while True:
    j_res = requests.get(f"{BASE_URL}/api/jobs/{job_id}", headers=HEADERS)
    j_data = j_res.json()
    status = j_data.get("status")
    print(f"Status: {status}...")
    
    if status == "success":
        print(f"Job completed successfully!")
        result = j_data.get("result", {})
        
        if result and isinstance(result, str):
            result = json.loads(result)
            
        file_path_saved = result.get('file_path')
        print(f"File Path saved in DB: {file_path_saved}")
        
        if file_path_saved and "paperless:" in file_path_saved:
            print("SUCCESS: Paperless ID detected!")
            
            # 3. Test Download Proxy Endpoint
            print(f"\n3. Testing Download Proxy for {file_path_saved}...")
            # We must encode or url-encode if needed, but the endpoint takes the filename direct
            dl_url = f"{BASE_URL}/api/files/{file_path_saved}?token={API_KEY}"
            dl_res = requests.get(dl_url, stream=True)
            if dl_res.status_code == 200:
                print(f"SUCCESS: Proxy downloaded {len(dl_res.content)} bytes of PDF data.")
                print(f"Content-Type: {dl_res.headers.get('Content-Type')}")
            else:
                print(f"ERROR: Proxy failed with {dl_res.status_code}: {dl_res.text}")
        else:
            print(f"Warning: File path is not a paperless ID. Is Paperless enabled?")
        
        break
    elif status == "error":
        print(f"Job failed: {j_data.get('error_message')}")
        break
        
    time.sleep(3)
