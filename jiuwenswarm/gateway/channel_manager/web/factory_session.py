"""Read-only activity projection for a factory home."""
import json
import os
from pathlib import Path

from jiuwenswarm.factory.redact import sanitize


def controller_is_locked(lock):
    """Observe the Linux lock table without contending with the controller."""
    try:
        stat = lock.stat()
        locks = Path('/proc/locks').read_text().splitlines()
    except OSError:
        return False
    identity = os.major(stat.st_dev), os.minor(stat.st_dev), stat.st_ino
    for line in locks:
        fields = line.split()
        if fields[1:4] != ['FLOCK', 'ADVISORY', 'WRITE']:
            continue
        major, minor, inode = fields[5].split(':')
        if (int(major, 16), int(minor, 16), int(inode)) == identity:
            return True
    return False


def transcript_activity(path, turn):
    latest = None
    parts = []
    tools = {}
    current_turn = None
    if not path.is_file():
        return latest, tools
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if not line.endswith('\n'):
                break  # The controller is still appending this record.
            row = json.loads(line)
            kind = row.get('event_type', row.get('event'))
            if kind == 'turn.start':
                current_turn = row.get('turn')
                parts = []
                tools.clear()
            elif kind == 'turn.end':
                tools.clear()
            elif kind == 'chat.tool_call' and current_turn == turn:
                call = row.get('tool_call') or {}
                if call.get('tool_call_id') and call.get('name'):
                    tools[call['tool_call_id']] = call['name']
            elif kind == 'chat.tool_result':
                tools.pop(row.get('tool_call_id'), None)
            elif kind in {'chat.delta', 'chat.final', 'native.progress'}:
                content = row.get('content')
                if not isinstance(content, str) or not content:
                    continue
                if kind in {'chat.final', 'native.progress'}:
                    parts = [content]
                else:
                    parts.append(content)
                if content.strip():
                    latest = parts, row.get('t')
    if latest is None:
        return None, tools
    parts, created = latest
    message = sanitize(''.join(parts).strip())
    if len(message) > 3200:
        message = message[:3200] + '…'
    return dict(text=message, created=created), tools


def session_snapshot(data, transcript, running, now):
    state = data['_meta']['controller_state']
    started, ended, tick = (state.get(key) for key in ('started', 'finished', 'tick'))
    outcome = state.get('outcome')
    elapsed = state.get('active_s')
    if elapsed is None and started is not None:
        stop = now if running else ended or tick
        if stop is not None:
            elapsed = max(0, stop - started)
    elif elapsed is not None and running and tick is not None:
        elapsed += max(0, now - tick)
    if running:
        status = 'running'
    elif outcome == 'waiting':
        status = 'waiting'
    elif ended is not None or outcome:
        status = 'finished'
    elif started is None:
        status = 'idle'
    else:
        status = 'unknown'
    turn = state.get('turns') or None
    latest, tools = transcript_activity(transcript, turn)
    step = None
    if status in {'running', 'waiting'}:
        active_jobs = [a for a in data.get('attempts', []) if a['state'] in {'running', 'queued', 'cancel_requested'}]
        if running and state.get('native_step'):
            step = dict(kind='job', label=state['native_step'])
        elif active_jobs:
            step = dict(kind='job', label=active_jobs[-1]['kind'])
        elif tools and running:
            step = dict(kind='tool', label=next(reversed(tools.values())))
        elif turn and running:
            step = dict(kind='turn', label=str(turn))
    return dict(status=status, elapsed_s=elapsed, turn=turn, step=step, latest_message=latest)
