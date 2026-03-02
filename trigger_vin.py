import requests
import json

url = "https://servicebox.autoleeb.at/api/maintenance-plan"
headers = {
    "X-Auth-Token": "SECRET_TOKEN_123",
    "Content-Type": "application/json"
}
data = {
    "vin": "VF3CCHMZ6HW053698"
}

print(f"Sending request for VIN: {data['vin']}...")
try:
    response = requests.post(url, headers=headers, json=data, timeout=300)
    print(f"Status Code: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
except Exception as e:
    print(f"Error: {e}")
