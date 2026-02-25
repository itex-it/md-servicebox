import requests

try:
    r = requests.get("https://servicebox.autoleeb.at/api/auth/me", timeout=5)
    print(f"Status Code: {r.status_code}")
    print(f"Response: {r.text}")
except Exception as e:
    print(f"Error: {e}")
