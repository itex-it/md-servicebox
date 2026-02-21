import requests
import json

BASE_URL = "http://localhost:8005"
HEADERS = {"X-Auth-Token": "SECRET_TOKEN_123"}

def check_history():
    try:
        res = requests.get(f"{BASE_URL}/api/history?limit=25", headers=HEADERS)
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            print(json.dumps(data, indent=2))
        else:
            print(res.text)
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    check_history()
