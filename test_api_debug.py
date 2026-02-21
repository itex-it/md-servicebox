import urllib.request
import json

url = "http://127.0.0.1:8000/api/maintenance-plan"
data = {"vin": "VF3EBRHD8BZ038648"}
json_data = json.dumps(data).encode("utf-8")

req = urllib.request.Request(url, data=json_data, headers={'Content-Type': 'application/json'}, method='POST')

try:
    print(f"Sending request to {url}...")
    with urllib.request.urlopen(req) as response:
        print(f"Status Code: {response.getcode()}")
        resp_body = response.read().decode('utf-8')
        print("Response JSON:")
        print(resp_body)
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print("Response Body:")
    print(e.read().decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
