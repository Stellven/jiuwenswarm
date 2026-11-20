#!/usr/bin/env python3
"""Stream one fixed chat prompt; retain full SSE and client TTFT evidence."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import time
import urllib.request

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--url', required=True)
p.add_argument('--arm', required=True)
p.add_argument('--prompt', type=Path, required=True)
p.add_argument('--prompt-tokens', type=int, required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('--repeat', type=int, default=0)
p.add_argument('--discard', action='store_true')
a = p.parse_args()
a.out.mkdir(parents=True, exist_ok=False)
body = {'messages':[{'role':'user','content':a.prompt.read_text()}], 'max_tokens':32, 'temperature':0, 'seed':1, 'stream':True, 'stream_options':{'include_usage':True}, 'cache_prompt':False, 'chat_template_kwargs':{'enable_thinking':False}}
(a.out/'request.json').write_text(json.dumps(body,indent=2)+'\n')
req = urllib.request.Request(a.url.rstrip('/')+'/v1/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
result = {'arm':a.arm,'prompt_tokens':a.prompt_tokens,'repeat':a.repeat,'discard':a.discard,'started':datetime.now(timezone.utc).isoformat(),'prompt_sha256':hashlib.sha256(a.prompt.read_bytes()).hexdigest(),'ttft_s':None,'first_content_s':None,'usage':{},'timings':{},'request_path':str(a.out/'request.json')}
text = ''
reasoning = ''
server_meta = {}
for parent in a.out.resolve().parents:
    if (parent/'start.json').exists():
        server_meta=json.loads((parent/'start.json').read_text()); break
ledger=Path.home()/'predemo-spark/OPS/LEDGER.jsonl'
def record(event, observation):
    row={'event':event, 'arm':a.arm, 'command':server_meta.get('command'), 'binary_sha256':server_meta.get('binary_sha256'), 'result_path':str(a.out.resolve()), **observation}
    with ledger.open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX); stream.write(json.dumps(row)+'\n')
record('request-start',result)
t0 = time.monotonic()
try:
    with urllib.request.urlopen(req,timeout=3600) as response, (a.out/'response.sse').open('wb') as raw:
        for line in response:
            raw.write(line); raw.flush()
            if not line.startswith(b'data:'):
                continue
            data = line[5:].strip()
            if data == b'[DONE]': break
            event = json.loads(data)
            if event.get('usage'): result['usage'] = event['usage']
            if event.get('timings'): result['timings'] = event['timings']
            for choice in event.get('choices',[]):
                delta=choice.get('delta') or {}
                piece=delta.get('content') or ''
                think=delta.get('reasoning_content') or ''
                if (piece or think) and result['ttft_s'] is None: result['ttft_s']=time.monotonic()-t0
                if piece and result['first_content_s'] is None: result['first_content_s']=time.monotonic()-t0
                text += piece; reasoning += think
                if choice.get('finish_reason'): result['finish_reason']=choice['finish_reason']
    try:
        with urllib.request.urlopen(a.url.rstrip('/')+'/v1/status',timeout=5) as response:
            status=json.load(response)
        (a.out/'status.json').write_text(json.dumps(status,indent=2)+'\n')
        if status.get('last_timings'):result['timings']=status['last_timings']
    except Exception:
        pass
    result['ok']=result['ttft_s'] is not None
except Exception as exc:
    result['ok']=False
    result['error']=repr(exc)
finally:
    result['wall_s']=time.monotonic()-t0
    result['output_sha256']=hashlib.sha256(text.encode()).hexdigest()
    result['reasoning_sha256']=hashlib.sha256(reasoning.encode()).hexdigest()
    result['decode_tps']=result['timings'].get('predicted_per_second')
    (a.out/'output.txt').write_text(text)
    (a.out/'reasoning.txt').write_text(reasoning)
    (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    record('request-stop',result)
    print(json.dumps(result,indent=2),flush=True)
raise SystemExit(0 if result['ok'] else 1)
