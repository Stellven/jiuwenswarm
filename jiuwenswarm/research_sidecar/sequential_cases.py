"""Small, versioned, human-reviewed sequential campaign input format."""
import json
import math
from pathlib import Path
import re

from .evidence import relative

VERSION = 'sequential-cases:1'
ID = re.compile(r'^[a-z0-9][a-z0-9_.-]{0,47}$')
DEFAULT_LIMITS = {'deadline_s': 3600, 'cancel_grace_s': 30, 'poll_s': 1,
                  'max_artifact_bytes': 128 * 1024 * 1024, 'max_total_bytes': 512 * 1024 * 1024,
                  'max_files': 4096, 'command_timeout_s': 60, 'command_memory_mb': 1024,
                  'command_cpu_s': 60, 'max_log_bytes': 1024 * 1024, 'archive_member_limit': 100000}
SECRET_NAME = re.compile(r'(?:API_?KEY|TOKEN|PASSWORD|SECRET|CREDENTIAL)', re.I)


def safe_relative(value):
    if not isinstance(value, str): raise ValueError('relative file path must be a string')
    return relative(value)


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('identity must use 1-48 lowercase letters, digits, dots, underscores or hyphens')
    return value


def limits(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_LIMITS):
        raise ValueError('unknown case limit')
    result = {**DEFAULT_LIMITS, **value}
    for key, number in result.items():
        if type(number) not in (int, float) or not math.isfinite(number) or number <= 0:
            raise ValueError('limits must be finite positive numbers: ' + key)
        if key in {'max_artifact_bytes', 'max_total_bytes', 'max_files', 'command_memory_mb', 'command_cpu_s', 'max_log_bytes', 'archive_member_limit'} and type(number) is not int:
            raise ValueError('integer limit required: ' + key)
    if result['max_artifact_bytes'] > result['max_total_bytes']:
        raise ValueError('artifact limit exceeds total bound')
    return result


def command(value, index):
    if not isinstance(value, dict) or set(value) - {'id', 'command', 'cwd', 'env', 'trusted', 'timeout_s', 'outputs'}:
        raise ValueError('unsupported command declaration')
    if value.get('trusted') is not True:
        raise ValueError('runner commands require explicit trusted: true; task-generated code belongs in the app')
    argv = value.get('command')
    if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x or '\x00' in x for x in argv):
        raise ValueError('command must be an explicit nonempty argv list')
    cwd = value.get('cwd', '.')
    if cwd != '.':
        safe_relative(cwd)
    env = value.get('env', {})
    if not isinstance(env, dict): raise ValueError('command env must contain explicit allowed values or from_env references')
    for key, env_value in env.items():
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key): raise ValueError('invalid allowed environment name')
        if isinstance(env_value, dict):
            if set(env_value) != {'from_env'} or not isinstance(env_value['from_env'], str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', env_value['from_env']):
                raise ValueError('environment references require one from_env name')
        elif not isinstance(env_value, str) or '\x00' in env_value:
            raise ValueError('environment values must be strings or from_env references')
        elif SECRET_NAME.search(key):
            raise ValueError('credential environment values require from_env references, never literal case secrets')
    if set(env) & {'LD_PRELOAD', 'LD_LIBRARY_PATH', 'PYTHONPATH', 'PYTHONSTARTUP'}:
        raise ValueError('runtime injection environment is not permitted')
    timeout = value.get('timeout_s', 60)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('finite command timeout required')
    outputs = value.get('outputs', [])
    if not isinstance(outputs, list):
        raise ValueError('outputs must be explicit relative file paths')
    for path in outputs:
        safe_relative(path)
    return {**value, 'id': identifier(value.get('id', 'command-' + str(index))), 'cwd': cwd,
            'env': env, 'timeout_s': timeout, 'outputs': outputs}


def validate_cases(document):
    if not isinstance(document, dict) or set(document) - {'schema_version', 'cases', 'policy', 'limits'} or document.get('schema_version') != VERSION:
        raise ValueError('expected schema_version: ' + VERSION)
    policy = document.get('policy', 'continue')
    if policy not in {'continue', 'stop'}:
        raise ValueError('policy must be continue or stop')
    rows = document.get('cases')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
        raise ValueError('1-1000 supplied cases required')
    result = []; seen = set()
    base_limits = limits(document.get('limits', {}))
    for row in rows:
        if not isinstance(row, dict) or set(row) - {'id', 'task', 'inputs', 'repeats', 'setup', 'steps', 'collection', 'limits', 'deadline_at', 'plan_source', 'collection_mode'}:
            raise ValueError('unknown case field')
        collection_mode = row.get('collection_mode', 'auto')
        if collection_mode not in ('auto', 'archive'):
            raise ValueError('collection_mode must be auto or archive')
        if 'plan_source' in row and row['plan_source'] not in ('static', 'planned'):
            raise ValueError('plan_source must be static or planned')
        ident = identifier(row.get('id'))
        if ident in seen:
            raise ValueError('duplicate case ID')
        seen.add(ident)
        if not isinstance(row.get('task'), str) or not row['task'].strip() or len(row['task']) > 1024 * 1024:
            raise ValueError('bounded task text required')
        repeats = row.get('repeats', 1)
        if type(repeats) is not int or not 1 <= repeats <= 1000:
            raise ValueError('repeats must be 1-1000')
        inputs = row.get('inputs', [])
        if not isinstance(inputs, list) or len(inputs) > 4096:
            raise ValueError('bounded explicit input list required')
        destinations = set(); normalized = []
        for item in inputs:
            if not isinstance(item, dict) or set(item) - {'path', 'kind', 'destination', 'upload'}:
                raise ValueError('inputs require path and optional kind/destination/upload')
            path = str(safe_relative(item.get('path', '')))
            destination = str(safe_relative(item.get('destination', path)))
            if destination in destinations:
                raise ValueError('conflicting input destination')
            destinations.add(destination)
            kind = item.get('kind', 'docs')
            if kind not in {'docs', 'repo', 'datasets'} or type(item.get('upload', True)) is not bool:
                raise ValueError('unsupported input kind or upload flag')
            normalized.append({'path': path, 'destination': destination, 'kind': kind, 'upload': item.get('upload', True)})
        phases = {}
        all_commands = set()
        for phase in ('setup', 'steps', 'collection'):
            commands = row.get(phase, [])
            if not isinstance(commands, list) or len(commands) > 128:
                raise ValueError('bounded command list required for ' + phase)
            phases[phase] = [command(v, n + 1) for n, v in enumerate(commands)]
            for declared in phases[phase]:
                key = phase + ':' + declared['id']
                if key in all_commands:
                    raise ValueError('duplicate command identity')
                all_commands.add(key)
        case_limits = limits({**base_limits, **row.get('limits', {})})
        deadline = row.get('deadline_at')
        if deadline is not None:
            from datetime import datetime
            if not isinstance(deadline, str) or datetime.fromisoformat(deadline.replace('Z', '+00:00')).tzinfo is None:
                raise ValueError('deadline_at must be an absolute timestamp with timezone')
        result.append({**row, **phases, 'id': ident, 'inputs': normalized, 'repeats': repeats,
                       'limits': case_limits, 'collection_mode': collection_mode})
    if sum(r['repeats'] for r in result) > 10000:
        raise ValueError('campaign exceeds 10000 sequential runs')
    return {'schema_version': VERSION, 'policy': policy, 'limits': base_limits, 'cases': result}


def load_cases(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('cases must be one bounded regular JSON/YAML file')
    raw = path.read_text(encoding='utf-8')
    if path.suffix.lower() == '.json':
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate JSON key: ' + key)
                result[key] = value
            return result
        document = json.loads(raw, object_pairs_hook=unique)
    elif path.suffix.lower() in {'.yaml', '.yml'}:
        from ruamel.yaml import YAML
        parser = YAML(typ='safe'); parser.allow_duplicate_keys = False
        document = parser.load(raw)
    else:
        raise ValueError('cases filename must end in .json, .yaml or .yml')
    return validate_cases(document)
