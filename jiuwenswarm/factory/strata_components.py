"""Pure, bounded configuration components for the pinned Strata Spark engine.

A returned profile is a candidate input, not an admitted job, correctness verdict,
or permission to alter an existing contract. No source patch is applied here.
"""
from __future__ import annotations

import copy
import hashlib
import json

SOURCE_REVISION = 'ffa80d73133ea5c548aefe57889a16e8085a938f'
COMPONENT = 'strata.verified_drafting'
ENV_KEYS = {'DS4_ASYNC_T', 'DS4_UMA_HEADROOM_GIB', 'DS4_STORE_GB', 'DS4_COPY_ALL',
            'DS4_AHEAD', 'DS4_ENGRAM_THREADS', 'DS4_ENGRAM_CACHE_MB', 'STRATA_DS4_REUSE'}


def _digest(profile):
    try:
        payload = json.dumps(profile, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError('base_profile must contain finite JSON data') from exc
    return hashlib.sha256(payload.encode()).hexdigest()


def _flag(args, name):
    if args.count(name) != 1:
        raise ValueError('Exactly one ' + name + ' setting is required')
    index = args.index(name)
    if index + 1 >= len(args) or args[index + 1].startswith('--'):
        raise ValueError('Missing value for ' + name)
    return args[index + 1], index + 1


def apply(base_profile, enabled):
    """Change only --dspark between explicit none/on under fixed Spark obligations."""
    if type(enabled) is not bool:
        raise ValueError('enabled must be a JSON boolean')
    if not isinstance(base_profile, dict):
        raise ValueError('base_profile must be a JSON object')
    before = _digest(base_profile)
    args = base_profile.get('args')
    if not isinstance(args, list) or not args or not all(isinstance(v, str) and v and '\0' not in v and '\n' not in v for v in args):
        raise ValueError('base_profile.args must be nonempty argument strings')
    if ('environment' in base_profile) == ('env' in base_profile):
        raise ValueError('Supply exactly one profile environment or env mapping')
    environment = base_profile.get('environment', base_profile.get('env'))
    if (not isinstance(environment, dict) or set(environment) - ENV_KEYS
            or any(not isinstance(v, str) or '\0' in v or '\n' in v for v in environment.values())):
        raise ValueError('Unsupported Strata component environment')
    required_env = {'STRATA_DS4_REUSE': '0', 'DS4_UMA_HEADROOM_GIB': '16',
                    'DS4_COPY_ALL': '0', 'DS4_STORE_GB': '0'}
    for key, expected in required_env.items():
        if environment.get(key) != expected:
            raise ValueError('Fixed ' + key + '=' + expected + ' is required')
    required_flags = {'--experts': '6', '--mmap-experts': 'on', '--cpu-threads': '8',
                      '--reserve-mib': '16384', '--vram-experts': '1.0'}
    for name, expected in required_flags.items():
        value, _ = _flag(args, name)
        if value != expected:
            raise ValueError('Fixed ' + name + ' ' + expected + ' is required')
    confidence, _ = _flag(args, '--dspark-conf')
    if confidence != '0.65':
        raise ValueError('Freeze --dspark-conf 0.65 in both arms before applying this component')
    if args.count('--no-expert-cache') != 1:
        raise ValueError('Static --no-expert-cache is required in both arms')
    if any('skip' in arg.lower() for arg in args if arg.startswith('--')):
        raise ValueError('Expert/layer skipping is outside this component')
    current, index = _flag(args, '--dspark')
    if current not in {'none', 'on'}:
        raise ValueError('Explicit --dspark none/on required; off/auto have different loading semantics')
    result = copy.deepcopy(base_profile)
    requested = 'on' if enabled else 'none'
    result['args'][index] = requested
    changed = current != requested
    return dict(profile=result, change=dict(
        component=COMPONENT, capsule='engine.strata_verified_drafting',
        source_revision=SOURCE_REVISION, mechanism='Native MTP drafting with target verification',
        changed=changed, changed_paths=['args[' + str(index) + ']'] if changed else [],
        setting='--dspark', before=current, after=requested,
        before_sha256=before, after_sha256=_digest(result), maximum_changed_variables=1,
        confidence_unchanged='0.65', full_experts=6, adaptive_expert_cache=False,
        status='candidate_profile_only', performance_benefit='unknown',
        required_evidence=['actual accepted/offered draft counters', 'same frozen public-task correctness gate',
                           'independent fresh-cell A/A control', 'quiet counterbalanced speed comparison'],
        authority='No jobs, source changes, contract mutation, promotion or new grants. Operator admission is separate.'))


def dispatch(inputs):
    if not isinstance(inputs, dict) or set(inputs) != {'base_profile', 'enabled'}:
        raise ValueError('apply requires exactly base_profile and enabled')
    return apply(inputs['base_profile'], inputs['enabled'])
