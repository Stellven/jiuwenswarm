"""Operator rendezvous for supervised observers. Disabled in ordinary runs.

The rendezvous grants no product authority. Only the parent process can release
the worker; killing a paused worker leaves its durable sequential claim intact.
"""
import asyncio
import json
import os
from pathlib import Path


async def rendezvous(event, row):
    root = os.environ.get('AI4R_RUNNER_CONTROL')
    if not root:
        return
    root = Path(root)
    plan = json.loads((root / 'plan.json').read_bytes())
    if plan.get('event') != event:
        return
    reached = root / 'worker' / (event + '.json')
    value = {k: row.get(k) for k in ('campaign_id', 'run_id', 'request_id', 'app_run_id')}
    value.update(event=event, pid=os.getpid())
    if not reached.exists():
        with reached.open('x') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush(); os.fsync(stream.fileno())
    while not (root / (event + '.release')).exists():
        await asyncio.sleep(.05)
