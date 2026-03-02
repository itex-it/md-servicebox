import requests
import json
import urllib3

# Warnungen fÃ¼r selbstsignierte Zertifikate unterdrÃ¼cken
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PORTAINER_URL = "https://194.242.35.77:9443"
API_KEY = "ptr_2nBOOFA629Rxcl/hubthc+IktGRr9QsUe1O5UR0NkS0="

def test_portainer_connection():
    url = f"{PORTAINER_URL}/api/endpoints"
    headers = {
        "X-API-Key": API_KEY
    }
    
    print(f"Versuche Lese-Zugriff auf Portainer unter {PORTAINER_URL}...")
    
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        
        if response.status_code == 200:
            endpoints = response.json()
            print("\nERFOLG! \u2705 Verbindung hergestellt.")
            print(f"Folgende Docker-Umgebungen (Endpoints) wurden gefunden ({len(endpoints)} StÃ¼ck):")
            for ep in endpoints:
                print(f" - ID: {ep.get('Id')} | Name: {ep.get('Name')} | Status: {'UP' if ep.get('Status') == 1 else 'DOWN'}")
            
            # Fetch stacks
            r_stacks = requests.get(f"{PORTAINER_URL}/api/stacks", headers=headers, verify=False, timeout=10)
            # Fetch stacks
            r_stacks = requests.get(f"{PORTAINER_URL}/api/stacks", headers=headers, verify=False, timeout=10)
            if r_stacks.status_code == 200:
                print("\nActive Stacks:")
                for s in r_stacks.json():
                    print(f" - ID: {s.get('Id')} | Name: {s.get('Name')}")
            else:
                print(f"Error fetching stacks: {r_stacks.status_code}")
        else:
            print(f"\nFEHLER! \u274C Zugriff abgelehnt oder Endpunkt nicht gefunden.")
            print(f"HTTP Status: {response.status_code}")
            print(f"Antwort: {response.text[:200]}")
            
    except requests.exceptions.RequestException as e:
        print(f"\nVERBINDUNGSFEHLER! \u274c")
        print(f"Konnte den Server nicht erreichen. Fehlerdetails: {e}")

if __name__ == "__main__":
    test_portainer_connection()
