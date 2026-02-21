import requests
import json
import urllib3

# Warnungen fuer selbstsignierte Zertifikate unterdruecken
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PORTAINER_URL = "https://194.242.35.77:9443"
API_KEY = "ptr_2nBOOFA629Rxcl/hubthc+IktGRr9QsUe1O5UR0NkS0="
ENDPOINT_ID = 3

def read_portainer_data():
    headers = {
        "X-API-Key": API_KEY,
        "Accept": "application/json"
    }
    
    print(f"Versuche Lese-Zugriff auf Portainer (https://194.242.35.77:9443)...")
    
    # 1. Stacks abfragen (Lesend)
    stacks_url = f"{PORTAINER_URL}/api/stacks"
    try:
        print("\n--- STACKS ---")
        response = requests.get(stacks_url, headers=headers, verify=False, timeout=10)
        if response.status_code == 200:
            stacks = response.json()
            if not stacks:
                print("Keine Stacks gefunden.")
            for s in stacks:
                print(f" - Stack: {s.get('Name')} (Status: {s.get('Status')})")
        else:
            print(f"Fehler beim Lesen der Stacks: {response.status_code}")
            
    except Exception as e:
        print(f"Verbindungsfehler bei Stacks: {e}")

    # 2. Container abfragen (Lesend auf Endpoint 3)
    containers_url = f"{PORTAINER_URL}/api/endpoints/{ENDPOINT_ID}/docker/containers/json"
    try:
        print("\n--- CONTAINERS (Endpoint 3) ---")
        response = requests.get(containers_url, headers=headers, verify=False, timeout=10)
        if response.status_code == 200:
            containers = response.json()
            if not containers:
                print("Keine Container gefunden.")
            # Zeige nur die ersten 5 an, um die Ausgabe uebersichtlich zu halten
            for c in containers[:5]:
                name = c.get('Names', ['Unknown'])[0].strip('/')
                state = c.get('State')
                image = c.get('Image')
                print(f" - Container: {name} | Image: {image} | Status: {state}")
            if len(containers) > 5:
                print(f" ... und {len(containers) - 5} weitere Container.")
        else:
            print(f"Fehler beim Lesen der Container: {response.status_code}")
            
    except Exception as e:
        print(f"Verbindungsfehler bei Containern: {e}")

if __name__ == "__main__":
    read_portainer_data()
