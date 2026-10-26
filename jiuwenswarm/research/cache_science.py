"""Capture explicitly supplied public cache traces and frozen root scoring profile."""
from __future__ import annotations
import hashlib
import platform
from pathlib import Path
from .contracts import ResearchError, validate
from .state import json_bytes

BASELINE = b"import json\nfrom pathlib import Path\nfrom collections import OrderedDict\n\ndef simulate_cache(data):\n    results = {}\n    for name, trace in data['traces'].items():\n        cache, seen, hits = OrderedDict(), set(), 0\n        for key in trace:\n            if key in cache:\n                hits += 1\n                cache.move_to_end(key)\n            else:\n                cache[key] = None\n                if len(cache) > data['capacity_entries']:\n                    cache.popitem(last=False)\n            seen.add(key)\n        results[name] = {'hits':hits,'misses':len(trace)-hits,'unbounded_misses':len(seen)}\n    return {'source_id':data['source_id'],'unit':'requests','results':results}\n\nprint(json.dumps(simulate_cache(json.loads(Path('/resources/validation/data.json').read_text()))))\n"

def capture_cache_science_resources(store, *, public_path):
    """Capture an explicitly supplied public package; never create example data."""
    from .cache_protocol import parse_cache_dataset
    source = Path(public_path)
    if (not source.is_absolute() or source.is_symlink() or not source.is_file()
            or source.stat().st_size > 2 * 1024 * 1024):
        raise ResearchError('external_dataset_invalid', 'An explicit bounded public data.json is required')
    data = source.read_bytes()
    parse_cache_dataset(data)
    requirements = store.put_blob(b'', media_type='text/plain')
    approval = store.put_blob(json_bytes({'schema': 'ai4r-local-environment-approval:1',
        'purpose': 'Externally supplied cache-study; Python standard library only; no third-party packages',
        'platform_fact': [platform.system(), platform.machine(), platform.python_version()]}), media_type='application/json')
    lock = {'schema_version': '1.0.0', 'id': 'external_cache_study_stdlib_environment',
        'platform': platform.system().lower() + '-' + platform.machine().lower(),
        'requirements_ref': requirements, 'package_refs': [], 'approval_ref': approval}
    validate('environment-lock', lock)
    lock_ref = store.put_record('environment-lock', lock)
    guide = b'# Captured cache study\n\nImplement simulate_cache(data) in poc_patch.py using only Python standard library.\nRead /resources/validation/data.json; use its capacity_entries and LRU replacement.\nProcess each named request trace independently with initially empty caches.\nEmit exactly one JSON object with source_id equal to the input source_id,\nunit requests, and results mapping every trace name to integer hits, misses,\nand unbounded_misses. hits and misses describe bounded LRU; unbounded_misses\ncounts first occurrences in an unbounded cache. No metrics or timing claims.\nThe immutable baseline also emits these complete observations; the protected\nhost independently recomputes every count, then selects unbounded_misses for\nthe baseline and bounded misses for treatment. miss_ratio is role-specific\nmisses / total requests over all traces, fraction, lower is better.\nRun baseline first then treatment, three repetitions each, fixed seed 42.\nBounded LRU cannot outperform an unbounded cache on misses; report the actual\nnegative or inconclusive result, uncertainty and limitations honestly.\nCounts do not establish latency or elapsed-time speedup. Preserve original stdout.\n'
    def snapshot(key, kind, names):
        value = {'schema_version': '1.0.0', 'id': key, 'kind': kind,
            'origin': 'Explicitly imported external public cache-study package',
            'revision': hashlib.sha256(b''.join(raw for _, raw, _ in names)).hexdigest(),
            'files': [{'path': name, 'artifact_ref': store.put_blob(raw, media_type=media),
                       'media_type': media, 'audience': 'researcher'} for name, raw, media in names],
            'access': 'read-only', 'license': 'User-supplied dataset; retain its original usage conditions',
            'availability': 'available', 'environment_ref': lock_ref}
        validate('resource-snapshot', value)
        return store.put_record('resource-snapshot', value)
    baseline = snapshot('baseline_resource', 'baseline code', [('baseline.py', BASELINE, 'text/x-python'),
        ('README.md', guide, 'text/markdown')])
    validation = snapshot('validation_resource', 'validation dataset', [('data.json', data, 'application/json')])
    workspace = store.put_blob(json_bytes({'schema': 'ai4r-local-poc-workspace:1', 'path': '/workspace/poc',
        'access': 'protected-root-broker-only execution; unprivileged generated code'}), media_type='application/json')
    rows = [('baseline_resource','file',baseline), ('validation_resource','dataset',validation),
            ('environment_lock','file',lock_ref), ('poc_workspace','workspace',workspace)]
    inventory = {'schema_version': '1.0.0', 'id': 'local_cpu_science_resources',
        'resources': [{'resource_key': key, 'kind': kind, 'available': True, 'quantity': 1, 'ref': ref} for key, kind, ref in rows]}
    validate('resource-inventory', inventory)
    guide_ref = next(row['artifact_ref'] for row in store.read_record(baseline)['files'] if row['path'] == 'README.md')
    from . import cache_protocol, trusted_cache
    scoring_profile = {'protocol': cache_protocol.PROTOCOL, 'public_dataset_ref': validation,
        'public_file':'data.json', 'public_data_sha256':hashlib.sha256(data).hexdigest(),
        'scorer_sha256':hashlib.sha256(Path(trusted_cache.__file__).read_bytes()).hexdigest(),
        'protocol_sha256':hashlib.sha256(Path(cache_protocol.__file__).read_bytes()).hexdigest(),
        'max_stdout_bytes':cache_protocol.MAX_BYTES}
    return {'resource_inventory_ref': store.put_record('resource-inventory', inventory),
        'run_inputs': {'baseline_resource': baseline, 'validation_resource': validation},
        'host_records': {'environment_lock': lock_ref},
        'resource_reads': [ref for _, _, ref in rows],
        'approved_environments': [{'lock_ref': lock_ref, 'approval_ref': approval,
            'platform_fact': [platform.system(), platform.machine(), platform.python_version()], 'wheel_filenames': {}}],
        'guide': guide.decode('utf-8'), 'guide_ref': guide_ref, 'local_example_ref': None,
        'scoring_profile': scoring_profile}
