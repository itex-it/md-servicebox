import requests
import json
import time

url = "http://localhost:8005/api/maintenance-plan"
headers = {
    "Content-Type": "application/json",
    "X-Auth-Token": "SECRET_TOKEN_123"
}
data = {
    "vin": "VF3EBRHD8BZ038648"
}

print(f"Sending request to {url}...")
try:
    start = time.time()
    response = requests.post(url, headers=headers, json=data, timeout=120)
    duration = time.time() - start
    
    print(f"Status Code: {response.status_code}")
    print(f"Duration: {duration:.2f}s")
    
    try:
        print("Response JSON:")
        print(json.dumps(response.json(), indent=2))
    except:
        print("Response text:", response.text)

except Exception as e:
    print(f"Request failed: {e}")
