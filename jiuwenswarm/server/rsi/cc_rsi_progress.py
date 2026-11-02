"""Closed public progress overlay; the web process never reads worker records."""
from datetime import datetime, timezone
import copy
import json
import math
import os
from pathlib import Path
import re
import stat
import time

from jiuwenswarm.research_rsi.progress import STAGES

SCHEMA = 'ai4r-cc-rsi-progress:1'
MAX_BYTES = 128 * 1024
FIELDS = {'schema', 'workspace_id', 'run_id', 'target_id', 'parent_hash', 'observed_at',
          'started_at', 'worker_status', 'events', 'iteration', 'max_iterations',
          'completed_iterations', 'model_calls', 'executions', 'execution_limit', 'limit_seconds'}
EVENT_FIELDS = {'id', 'at', 'stage', 'iteration', 'source'}


def validate(value, workspace):
    if not isinstance(value, dict) or set(value) != FIELDS or value['schema'] != SCHEMA or value['workspace_id'] != workspace:
        raise ValueError('Closed workspace progress required')
    for key in ('run_id', 'target_id'):
        if not isinstance(value[key], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}', value[key]):
            raise ValueError('Exact progress identity required')
    if not isinstance(value['parent_hash'], str) or not re.fullmatch('[a-f0-9]{64}', value['parent_hash']):
        raise ValueError('Exact parent required')
    if value['worker_status'] not in ('running', 'finalizing', 'failed'):
        raise ValueError('Observed worker status required')
    for key in ('observed_at', 'started_at', 'limit_seconds'):
        if type(value[key]) not in (int, float) or not math.isfinite(value[key]) or not 0 <= value[key] <= 1e10:
            raise ValueError('Finite progress timing required')
    for key in ('iteration', 'max_iterations', 'completed_iterations', 'model_calls', 'executions', 'execution_limit'):
        n = value[key]
        if n is not None and (type(n) is not int or not 0 <= n <= 1000000):
            raise ValueError('Finite progress count required')
    if not isinstance(value['events'], list) or not 1 <= len(value['events']) <= 256:
        raise ValueError('Bounded progress events required')
    for event in value['events']:
        if not isinstance(event, dict) or set(event) != EVENT_FIELDS:
            raise ValueError('Closed progress event required')
        if event['stage'] not in STAGES or event['source'] not in ('engine', 'observation'):
            raise ValueError('Known stage and source required')
        if not isinstance(event['id'], str) or not re.fullmatch('[a-f0-9]{64}', event['id']):
            raise ValueError('Exact event identity required')
        if type(event['at']) not in (int, float) or not math.isfinite(event['at']) or not 0 <= event['at'] <= 1e10:
            raise ValueError('Finite event time required')
        if event['iteration'] is not None and (type(event['iteration']) is not int or not 0 <= event['iteration'] <= 100):
            raise ValueError('Finite iteration required')
    return value


def iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def overlay(view, values, *, now=None):
    """Completed publications always win, even against a newer stale heartbeat."""
    now = time.time() if now is None else now
    view = copy.deepcopy(view)
    terminal_ids = {run['id'] for run in view['runs']}
    for value in values:
        if value['run_id'] in terminal_ids:
            continue
        stale = now - value['observed_at'] > 20 or value['observed_at'] > now + 5
        events = sorted(value['events'], key=lambda row: (row['at'], row['id']))
        latest = events[-1]
        status = 'UNKNOWN' if stale else value['worker_status'].upper()
        activity = [{'id': row['id'], 'at': iso(row['at']), 'stage': STAGES[row['stage']],
                     'status': ('running' if index == len(events) - 1 else 'recorded'),
                     'summary': ('Engine entered ' if row['source'] == 'engine' else 'Observed work: ')
                                + STAGES[row['stage']] + (f" · round {row['iteration']}" if row['iteration'] else '')}
                    for index, row in enumerate(events)]
        run = {'id': value['run_id'], 'target_id': value['target_id'], 'stage': STAGES[latest['stage']],
               'status': status, 'blockers': ['Progress updates are stale; current stage is unconfirmed.'] if stale else [],
               'budget': {'elapsed_seconds': max(0, value['observed_at'] - value['started_at']),
                          'limit_seconds': value['limit_seconds'], 'setup_calls': None, 'diagnosis_calls': None,
                          'proposal_calls': None, 'generation_call_limit': None, 'cost': None, 'currency': None},
               'activity': activity, 'progress': {key: value[key] for key in (
                   'observed_at', 'iteration', 'max_iterations', 'completed_iterations', 'model_calls', 'executions', 'execution_limit')}}
        run['progress'].update(stale=stale, source=latest['source'])
        if not any(row['id'] == value['target_id'] for row in view['targets']):
            view['targets'].append({'id': value['target_id'], 'name': value['target_id'],
                'parent_hash': value['parent_hash'], 'active_hash': None,
                'run': {'allowed': False, 'blocker': 'A run has already been launched.'}})
        view['runs'].append(run)
    return view


def read_overlay(view, publication, workspace):
    """Only root-published bounded files under the already verified RO mount."""
    from .cc_rsi_projection import _root_ancestors
    directory = Path(publication).parent / 'live'
    try:
        _root_ancestors(directory / 'entry.json')
        paths = sorted(directory.glob('*.json'))
        if len(paths) > 256:
            return view
    except (OSError, ValueError):
        return view
    values = []
    for path in paths:
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                meta = os.fstat(fd)
                if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0 or meta.st_nlink != 1 or meta.st_mode & 0o022 or meta.st_size > MAX_BYTES:
                    continue
                with os.fdopen(fd, 'rb', closefd=False) as stream:
                    raw = stream.read(MAX_BYTES + 1)
            finally:
                os.close(fd)
            value = validate(json.loads(raw), workspace)
            if path.name != value['run_id'] + '.json':
                continue
            values.append(value)
        except (OSError, ValueError, TypeError, KeyError):
            continue  # A broken optional feed never hides completed evidence.
    return overlay(view, values)
