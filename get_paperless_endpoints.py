import sys
import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {'X-API-Key': 'ptr_JWr1CF0KKRLuu7px/14Tre0BvFWo2N9CS/SeipHR3IU='}

try:
    req = urllib.request.Request('https://10.254.254.95:9443/api/endpoints/3/docker/containers/json?all=1', headers=headers)
    with urllib.request.urlopen(req, context=ctx) as r:
        containers = json.loads(r.read())
        for c in containers:
            if "nginx-proxy-manager" in c['Names'][0]:
                print(c['Id'])
except Exception as e:
    print(e)
