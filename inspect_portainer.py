import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PORTAINER_URL = "https://194.242.35.77:9443"
API_KEY = "ptr_2nBOOFA629Rxcl/hubthc+IktGRr9QsUe1O5UR0NkS0="
ENDPOINT_ID = 3

def inspect_environment():
    headers = {
        "X-API-Key": API_KEY,
        "Accept": "application/json"
    }
    
    print("=== PORTAINER ENVIRONMENT INSPECTION ===")
    
    # 1. Get Networks
    networks_url = f"{PORTAINER_URL}/api/endpoints/{ENDPOINT_ID}/docker/networks"
    try:
        res = requests.get(networks_url, headers=headers, verify=False, timeout=10)
        res.raise_for_status()
        networks = res.json()
        print("\n--- NETWORKS ---")
        for net in networks:
            name = net.get('Name')
            driver = net.get('Driver')
            if name not in ['bridge', 'host', 'none'] and not name.startswith('portainer'):
                print(f"Network: {name} (Driver: {driver})")
    except Exception as e:
        print(f"Failed to fetch networks: {e}")

    # 2. Get Containers & Labels (to detect Reverse Proxies like Traefik/NPM)
    containers_url = f"{PORTAINER_URL}/api/endpoints/{ENDPOINT_ID}/docker/containers/json?all=1"
    try:
        res = requests.get(containers_url, headers=headers, verify=False, timeout=10)
        res.raise_for_status()
        containers = res.json()
        print("\n--- CONTAINERS & REVERSE PROXIES ---")
        
        proxy_found = False
        for c in containers:
            name = c.get('Names', ['Unknown'])[0].strip('/')
            image = c.get('Image', '')
            state = c.get('State')
            labels = c.get('Labels', {})
            ports = c.get('Ports', [])
            
            # Detect Proxy Managers
            if any(x in image.lower() for x in ['traefik', 'nginx-proxy-manager', 'nginx', 'caddy', 'npm']):
                proxy_found = True
                print(f"\n[DETECTED PROXY] {name} (Image: {image}, State: {state})")
                if ports:
                    port_bindings = ", ".join([f"{p.get('PublicPort', '?')}->{p.get('PrivatePort', '?')}" for p in ports if p.get('PublicPort')])
                    print(f"  Ports: {port_bindings}")
                
            # Print Traefik labels if any other container has them
            traefik_labels = {k: v for k, v in labels.items() if 'traefik' in k.lower()}
            if traefik_labels and 'traefik' not in image.lower():
                print(f"\n[ROUTED SERVICE] {name} has Traefik routing labels!")
                
        if not proxy_found:
            print("No obvious reverse proxy (Traefik, NPM, Nginx) detected in container names/images.")
            
    except Exception as e:
        print(f"Failed to fetch containers: {e}")

if __name__ == "__main__":
    inspect_environment()
