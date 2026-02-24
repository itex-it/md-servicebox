import sys
import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'X-API-Key': 'ptr_JWr1CF0KKRLuu7px/14Tre0BvFWo2N9CS/SeipHR3IU=',
    'Content-Type': 'application/json'
}

c_id = "98a8aabd72dc31ccd7fd89c9f5a24c941959953eb3aad3f5bffc7654f321f41e"
url_exec = f"https://10.254.254.95:9443/api/endpoints/3/docker/containers/{c_id}/exec"
exec_data = {
    "AttachStdout": True,
    "AttachStderr": True,
    "Cmd": ["sh", "-c", "cat /data/nginx/proxy_host/7.conf && ls -l /data/nginx/custom/"]
}

try:
    req_exec = urllib.request.Request(url_exec, data=json.dumps(exec_data).encode(), headers=headers, method='POST')
    with urllib.request.urlopen(req_exec, context=ctx) as r:
        exec_id = json.loads(r.read())["Id"]

    url_start = f"https://10.254.254.95:9443/api/endpoints/3/docker/exec/{exec_id}/start"
    start_data = {"Detach": False, "Tty": False}
    req_start = urllib.request.Request(url_start, data=json.dumps(start_data).encode(), headers=headers, method='POST')
    with urllib.request.urlopen(req_start, context=ctx) as r:
        print(r.read().decode('utf-8', errors='replace'))
except Exception as e:
    print(e)
