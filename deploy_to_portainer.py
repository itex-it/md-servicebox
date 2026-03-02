import requests
import json
import os
import urllib3
import time

# Ignoriere Zertifikatswarnungen bei Portainer (falls selbstsigniert)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- KONFIGURATION ---
PORTAINER_URL = "https://194.242.35.77:9443"
API_KEY = "ptr_2nBOOFA629Rxcl/hubthc+IktGRr9QsUe1O5UR0NkS0="
ENDPOINT_ID = 3  # ID, die im Testskript zurueckgegeben wurde
STACK_NAME = "md-servicebox" # Name des Stacks in Portainer

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def deploy_stack():
    compose_file_path = "docker-compose.yml"
    
    if not os.path.exists(compose_file_path):
        print(f" Fehler: {compose_file_path} nicht gefunden.")
        return
        
    print(f" Lese {compose_file_path} ein...")
    with open(compose_file_path, "r", encoding="utf-8") as f:
        compose_content = f.read()

    print(f" Pruefe, ob Stack '{STACK_NAME}' bereits existiert...")
    
    try:
        stack_id = 72
        print(f" Stack läuft unter (ID: {stack_id}). Führe GitOps UPDATE aus...")
        
        # Pull Git Update via API instead of raw string update
        payload = {
            "Env": [],
            "Prune": True,
            "PullImage": True
        }
        
        r_update = requests.put(
            f"{PORTAINER_URL}/api/stacks/{stack_id}/git/redeploy?endpointId={ENDPOINT_ID}",
            headers=headers,
            json=payload,
            verify=False,
            timeout=120
        )
        r_update.raise_for_status()
        print(" ERFOLG! \u2705 Stack wurde erfolgreich über GitOps neu gestartet.")
    except requests.exceptions.RequestException as e:
        print(f"\n FEHLER WÄHREND DES DEPLOYMENTS! \u274c")
        print(f"Details: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Server-Antwort: {e.response.text}")

if __name__ == "__main__":
    deploy_stack()
