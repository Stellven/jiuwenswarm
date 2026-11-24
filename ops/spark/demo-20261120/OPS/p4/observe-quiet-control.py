"""Sample overlapping jobs for the amended A+60 scope without touching model files."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

root = Path(__file__).resolve().parents[2]
scope = root / 'OPS/runs/p4-cache60-aplus-pass-2-quiet-01'
browser = {'chromium', 'chrome', 'chromium-browser', 'firefox', 'chrome-headless-shell', 'headless_shell'}
with (scope / 'host-activity.jsonl').open('x', buffering=1) as out:
    while not (scope / 'result.json').exists():
        processes = subprocess.check_output(['ps', '-eo', 'pid=,comm=,ni=,args='], text=True)
        found = []
        for line in processes.splitlines():
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            pid, name, nice, args = parts
            if name in browser or name.startswith('chrome-headless') or name in {'rsync', 'scp', 'rclone', 'sftp-server'}:
                found.append({'pid':int(pid), 'name':name, 'nice':int(nice)})
        print(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),'browsers_or_transfer_processes':found}),file=out)
        time.sleep(10)
