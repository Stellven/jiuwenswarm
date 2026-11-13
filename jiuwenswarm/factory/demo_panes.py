"""Side panes for a recorded factory run: what the agent reads/calls through CCs, and the source it changed.

    python -m jiuwenswarm.factory.demo_panes cc TASK_ID       # CC guidance read + capability calls, live
    python -m jiuwenswarm.factory.demo_panes source TASK_ID   # owned-checkout commits, diff stat, built images

Read-only: tails telemetry/events.jsonl and the task's owned git checkout. Colours follow the demo
vocabulary (plain grey, CC-guided change amber, confirmed green, failures red).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

GREY, AMBER, GREEN, RED, BOLD = '90', '33', '32', '31', '1'


def home():
    return Path(os.environ.get('FACTORY_HOME', '~/.jiuwenswarm-factory')).expanduser()


def say(color, text):
    print(f'\033[{color}m{text}\033[0m', flush=True)


def cc_feed(task_id, width=78):
    path = home() / 'telemetry' / 'events.jsonl'
    say(BOLD, ' CC activity · guidance the agent reads, capabilities it calls')
    with open(path, encoding='utf-8') as handle:
        handle.seek(0, 2)
        # Show this task's history first (if any), then follow.
        handle.seek(0)
        turn = None
        while True:
            line = handle.readline()
            if not line:
                time.sleep(1)
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get('task_id') != task_id:
                continue
            stamp = time.strftime('%H:%M', time.localtime(event.get('ts', 0)))
            if event.get('turn') != turn and event.get('turn') is not None:
                turn = event['turn']
                say(GREY, f' ── agent turn {turn} ' + '─' * 20)
            kind = event.get('event')
            if kind == 'cc.material':
                capsule = (event.get('capsule') or '').removeprefix('factory.')
                say(AMBER, f' {stamp} read  {capsule} · {event.get("material")}'[:width])
            elif kind == 'cc.call':
                capsule = (event.get('capsule') or '').removeprefix('factory.')
                ok = event.get('outcome') == 'ok'
                code = '' if ok else f' {event.get("error_code")}'
                say(GREY if ok else RED, f' {stamp} call  {event.get("capability")}  [{capsule}]{code}'[:width])
            elif kind == 'build.result':
                say(AMBER, f' {stamp} built image {str(event.get("image_id", "?")).removeprefix("sha256:")[:12]}')
            elif kind == 'ab.result':
                say(GREEN if event.get('gate') == 'improved' else BOLD,
                    f' {stamp} A/B  gate {event.get("gate")} · ratio {event.get("ratio")} · {event.get("per_arm_ms")}'[:width])
            elif kind == 'decision':
                say(AMBER, f' {stamp} decision rev {event.get("rev")} · {event.get("action_type", event.get("type", ""))}'[:width])


def git(checkout, *args):
    return subprocess.run(['git', '-C', str(checkout), *args], capture_output=True, text=True).stdout.strip()


def source_feed(task_id, base='cf34d3113', width=78):
    from .story import load_source
    task = load_source(task_id)['tasks'][0]
    branch = task['source']['branch']
    checkout = home() / 'agent-workspace' / task['source'].get('subpath', 'llama.cpp')
    shown = None
    while True:
        head = git(checkout, 'rev-parse', '--short=8', branch)
        images = [o for o in load_source(task_id).get('observations', [])
                  if o.get('kind') == 'build_result' and o.get('values', {}).get('image_id')]
        state = (head, len(images))
        if state != shown:
            shown = state
            print('\033[2J\033[H', end='')
            say(BOLD, f' Source · branch {branch} · plain base {base} (grey) → CC changes (amber)')
            for line in git(checkout, 'log', '--reverse', '--format=%h %s', f'{base}..{branch}').splitlines()[-8:]:
                say(AMBER, ' ' + line[:width - 1])
            if head == git(checkout, 'rev-parse', '--short=8', base):
                say(GREY, f' {base} plain llama.cpp (no changes yet)')
            stat = git(checkout, 'diff', '--shortstat', base, branch)
            if stat:
                say(AMBER, ' diff vs plain: ' + stat.strip())
                for line in git(checkout, 'diff', '--stat=76', base, branch).splitlines()[:-1][-7:]:
                    say(GREY, ' ' + line[:width - 1])
            for o in images[-3:]:
                v = o.get('values', {})
                say(AMBER, f' image {str(v.get("image_id", "?")).removeprefix("sha256:")[:12]}'
                           f'')
        time.sleep(3)


if __name__ == '__main__':
    mode, task = sys.argv[1], sys.argv[2]
    try:
        {'cc': cc_feed, 'source': source_feed}[mode](task)
    except KeyboardInterrupt:
        pass
