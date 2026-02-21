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
STACK_NAME = "servicebox" # Name des Stacks in Portainer

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
    
    # 1. Alle Stacks abrufen
    try:
        r_stacks = requests.get(f"{PORTAINER_URL}/api/stacks", headers=headers, verify=False, timeout=10)
        r_stacks.raise_for_status()
        stacks = r_stacks.json()
        
        existing_stack = next((s for s in stacks if s.get("Name") == STACK_NAME), None)
        
        if existing_stack:
            stack_id = existing_stack["Id"]
            print(f" Stack existiert bereits (ID: {stack_id}). Führe UPDATE aus...")
            
            # Update Stack Payload
            payload = {
                "StackFileContent": compose_content,
                "Env": [],
                "Prune": True
            }
            
            r_update = requests.put(
                f"{PORTAINER_URL}/api/stacks/{stack_id}?endpointId={ENDPOINT_ID}",
                headers=headers,
                json=payload,
                verify=False,
                timeout=30
            )
            r_update.raise_for_status()
            print(" ERFOLG! \u2705 Stack wurde erfolgreich geupdated und wird neu gestartet.")
            
        else:
            print(f" Stack '{STACK_NAME}' existiert nicht. Fuehre NEU-ERSTELLUNG (CREATE) aus...")
            
            # Bei Create als "Standalone/String" muss Portainer eine leicht andere Struktur haben (als "Form Data" oder Type 2)
            # FÃ¼r API v2.x Type 2 (Standalone/Swarm)
            payload = {
                "Name": STACK_NAME,
                "StackFileContent": compose_content,
                "Env": []
            }
            
            create_url = f"{PORTAINER_URL}/api/stacks/create/standalone/string?endpointId={ENDPOINT_ID}"
            r_create = requests.post(
                create_url,
                headers=headers,
                json=payload,
                verify=False,
                timeout=30
            )
            r_create.raise_for_status()
            print(" ERFOLG! \u2705 Stack wurde komplett neu erstellt und Container fahren jetzt hoch.")

    except requests.exceptions.RequestException as e:
        print(f"\n FEHLER WÄHREND DES DEPLOYMENTS! \u274c")
        print(f"Details: {e}")
        if hasattr(e.response, 'text') and e.response:
            print(f"Server-Antwort: {e.response.text}")

if __name__ == "__main__":
    deploy_stack()
