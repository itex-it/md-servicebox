import urllib.request
import ssl
import json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'X-API-Key': 'ptr_2nBOOFA629Rxcl/hubthc+IktGRr9QsUe1O5UR0NkS0=',
    'Content-Type': 'application/json'
}

# Find container ID of servicebox-app
url_find = "https://194.242.35.77:9443/api/endpoints/3/docker/containers/json?all=1"
req_find = urllib.request.Request(url_find, headers=headers)
with urllib.request.urlopen(req_find, context=ctx) as r:
    containers = json.loads(r.read())

c_id = None
for c in containers:
    if "/servicebox-app" in c.get("Names", []):
        c_id = c["Id"]
        break

if not c_id:
    print("Could not find servicebox-app container")
    exit(1)

# Create exec instance
url_exec = f"https://194.242.35.77:9443/api/endpoints/3/docker/containers/{c_id}/exec"
exec_data = {
    "AttachStdout": True,
    "AttachStderr": True,
    "Cmd": ["python", "-c", "import requests; print(requests.get('https://91.112.56.68/', headers={'Host': 'paperless.itex.at'}, verify=False).text[:500])"]
}
req_exec = urllib.request.Request(url_exec, data=json.dumps(exec_data).encode(), headers=headers, method='POST')
with urllib.request.urlopen(req_exec, context=ctx) as r:
    exec_id = json.loads(r.read())["Id"]

# Start exec instance
url_start = f"https://194.242.35.77:9443/api/endpoints/3/docker/exec/{exec_id}/start"
start_data = {"Detach": False, "Tty": False}
req_start = urllib.request.Request(url_start, data=json.dumps(start_data).encode(), headers=headers, method='POST')
with urllib.request.urlopen(req_start, context=ctx) as r:
    print(r.read().decode('utf-8', errors='replace'))
