import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PORTAINER_URL = "https://194.242.35.77:9443"
API_KEY = "ptr_2nBOOFA629Rxcl/hubthc+IktGRr9QsUe1O5UR0NkS0="
ENDPOINT_ID = 3

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def force_delete_stacks():
    print("Starte Löschung der defekten Stacks 27 & 28...")
    
    for stack_id in [27, 28]:
        print(f"Lösche Stack {stack_id}...")
        try:
            r = requests.delete(
                f"{PORTAINER_URL}/api/stacks/{stack_id}?endpointId={ENDPOINT_ID}",
                headers=headers,
                verify=False,
                timeout=10
            )
            if r.status_code == 204:
                print(f" -> Stack {stack_id} erfolgreich gelöscht!")
            elif r.status_code == 404:
                print(f" -> Stack {stack_id} existiert nicht mehr.")
            else:
                print(f" -> Fehler beim Löschen {stack_id}: {r.status_code} - {r.text}")
        except Exception as e:
            print(f" -> Verbindungsfehler bei Stack {stack_id}: {e}")

if __name__ == "__main__":
    force_delete_stacks()
