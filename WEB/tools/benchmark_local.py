"""Local server baseline; this does NOT measure the Wi-Fi radio path."""
import argparse
import json
import time
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:8001')
parser.add_argument('--seconds', type=float, default=10)
args = parser.parse_args()

def api(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(args.url+'/api/vision/'+path, data=data, headers={'Content-Type':'application/json'})
    with urlopen(request, timeout=15) as response:
        return json.load(response)

results = []
try:
    for mode in ('camera', 'raw', 'ai'):
        api('stop', {})
        api('start', {'mode':mode})
        time.sleep(3)
        first = api('status')
        started = time.monotonic()
        time.sleep(args.seconds)
        last = api('status')
        elapsed = time.monotonic()-started
        result = {'mode':mode, 'seconds':elapsed, 'frames':last['sequence']-first['sequence'],
                  'fps':(last['sequence']-first['sequence'])/elapsed, 'camera':last.get('camera'),
                  'jpeg_ms':last['jpeg_ms'], 'jpeg_bytes':last['jpeg_bytes'], 'error':last['error'],
                  'faces':last['faces']}
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
finally:
    api('stop', {})
    api('start', {'mode':'ai'})
