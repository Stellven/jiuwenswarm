"""Explicit, small local CPU research resources and exact runtime capture.

This is a labelled educational project, not a surrogate for a user's uploaded
dataset or an admission/qualification result. Metrics are measured by Benchmark.
"""
from __future__ import annotations

import hashlib
import os
import platform
import sys
from pathlib import Path

from .contracts import ResearchError, validate
from .state import json_bytes


BASELINE = b'''import json
from pathlib import Path
data = json.loads(Path('/resources/validation/data.json').read_text())
labels = [row['label'] for row in data['train']]
majority = max(sorted(set(labels)), key=labels.count)
accuracy = sum(row['label'] == majority for row in data['test']) / len(data['test'])
print(json.dumps({'metrics': {'accuracy': accuracy}}))
'''

SAMPLE_REQUEST = (
    'Using the built-in local CPU classification project and its captured train/test data, '
    'replace the majority-class classifier with a threshold at the midpoint between training class means. '
    'Keep the baseline, held-out test split and accuracy measurement unchanged. '
    'Use only the Python standard library, no network or GPU. Metric accuracy (fraction), higher is better; '
    'success if treatment accuracy > baseline accuracy, falsification if treatment accuracy <= baseline accuracy. '
    'Run the baseline first then the treatment, 3 repeats each, fixed seed 42. '
    'Deliver a report, POC files, raw logs and limitations.')


def capture_local_science_resources(store):
    """Capture actual authored bytes and a stdlib-only, offline environment."""
    requirements = store.put_blob(b'', media_type='text/plain')
    approval = store.put_blob(json_bytes({'schema': 'ai4r-local-environment-approval:1',
        'purpose': 'Local CPU tutorial; Python standard library only; no third-party packages',
        'platform_fact': [platform.system(), platform.machine(), platform.python_version()]}), media_type='application/json')
    lock = {'schema_version': '1.0.0', 'id': 'local_cpu_stdlib_environment',
        'platform': platform.system().lower() + '-' + platform.machine().lower(),
        'requirements_ref': requirements, 'package_refs': [], 'approval_ref': approval}
    validate('environment-lock', lock)
    lock_ref = store.put_record('environment-lock', lock)
    data = json_bytes({'description': 'Authored educational one-dimensional binary classification data; not external evidence',
        'train': [{'x': -3.0, 'label': 0}, {'x': -2.0, 'label': 0}, {'x': -1.0, 'label': 0},
                  {'x': 1.0, 'label': 1}, {'x': 2.0, 'label': 1}, {'x': 3.0, 'label': 1}],
        'test': [{'x': -2.5, 'label': 0}, {'x': -0.5, 'label': 0}, {'x': 0.5, 'label': 1}, {'x': 2.5, 'label': 1}]})
    guide = b'''# Local CPU classification project

This built-in educational project has actual captured Python and JSON files.
The baseline always predicts the training majority class. Improve only the
classifier in poc_patch.py, for example by fitting the midpoint between class
means on the training split. Preserve the held-out test split, the accuracy
measurement, baseline, and decision thresholds. Metric ID is accuracy (fraction,
higher is better). Use no dependencies, network, GPUs, or external data. Run the
frozen baseline first and then the treatment, at least three repeats each. A
successful result requires treatment accuracy > baseline accuracy; equality or
lower falsifies the improvement claim. Report genuine measured values and the
limitations of this tiny authored demonstration. Data is /resources/validation/data.json.
'''
    def snapshot(key, kind, names):
        value = {'schema_version': '1.0.0', 'id': key, 'kind': kind,
            'origin': 'AI4Research explicitly selected local educational project',
            'revision': hashlib.sha256(b''.join(raw for _, raw, _ in names)).hexdigest(),
            'files': [{'path': name, 'artifact_ref': store.put_blob(raw, media_type=media),
                       'media_type': media, 'audience': 'researcher'} for name, raw, media in names],
            'access': 'read-only', 'license': 'CC0-1.0 (authored local example)',
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
    example_ref = store.put_blob(json_bytes({'schema': 'ai4r-local-research-example:1',
        'id': 'local-cpu-classification', 'title': 'Improve a small classifier',
        'description': 'A real CPU experiment on explicitly authored educational data. No GPU or external dependencies required.',
        'filename': 'local_cpu_classification.md', 'guide_ref': guide_ref, 'request': SAMPLE_REQUEST,
        'baseline_resource_ref': baseline, 'validation_resource_ref': validation,
        'environment_lock_ref': lock_ref}), media_type='application/json')
    return {'resource_inventory_ref': store.put_record('resource-inventory', inventory),
        'run_inputs': {'baseline_resource': baseline, 'validation_resource': validation},
        'host_records': {'environment_lock': lock_ref},
        'resource_reads': [ref for _, _, ref in rows],
        'approved_environments': [{'lock_ref': lock_ref, 'approval_ref': approval,
            'platform_fact': [platform.system(), platform.machine(), platform.python_version()], 'wheel_filenames': {}}],
        'guide': guide.decode('utf-8'), 'guide_ref': guide_ref, 'local_example_ref': example_ref}


def capture_local_science_runtime(store, *, configuration_ref, policy_ref, resource_inventory_ref,
                                  entries, approved_environments):
    """Pin genuine active admissions; a captured record grants no execution."""
    from .native_ports import verify_installed_build
    bindings = []
    for entry in entries:
        declaration_ref = entry['declaration_ref']
        declaration = store.read_record(declaration_ref, contract_id='capsule-declaration')
        if declaration['identity']['name'] not in {'research.builder', 'research.benchmark'}:
            # Model-only workers/reviewers receive no scientific operation.
            # Whole-parent resource inspection still validates every sibling.
            continue
        admission = store.read_record(entry['admission_ref'], contract_id='library-admission')
        if admission['status'] != 'admitted' or admission['candidate_ref'] != declaration_ref or entry['standing'] != 'active':
            raise ResearchError('local_science_admission', 'Scientific binding requires an actual active exact admission')
        body_refs = entry['body_refs']
        implementations = [body_refs[row['path']] for row in declaration['identity']['body']]
        dependencies = [body_refs[pin['ref']] for row in declaration['needs']['external']
            for key in ('pin','lockfile') if (pin := row.get(key))]
        bindings.append({'configuration_ref': configuration_ref, 'policy_ref': policy_ref,
            'resource_inventory_ref': resource_inventory_ref, 'declaration_ref': declaration_ref,
            'implementation_refs': implementations, 'dependency_refs': dependencies,
            'admission_ref': entry['admission_ref'],
            'operations': ['provision','hardware_inventory','measure_job','run']
                if declaration['identity']['name'] == 'research.benchmark' else ['collect_builder']})
    value = {'schema': 'ai4r-science-runtime:2', 'id': 'local-cpu-science-' + verify_installed_build()[:16],
        'build_id': verify_installed_build(), 'gpu_required': False,
        'profile': {'asset_root': '/var/lib/ai4r-executor/assets',
            'environment_root': '/var/lib/ai4r-executor/environments', 'memory_mb': 1024, 'pids_max': 64,
            'run_timeout_s': 60, 'provision_timeout_s': 60, 'baseline_arguments': [], 'treatment_arguments': [],
            'uv_path': '/usr/local/bin/uv', 'python_path': sys._base_executable},
        'approved_environments': approved_environments, 'execution_bindings': bindings}
    from .science_runtime import decode_science_runtime_record
    decode_science_runtime_record(value)
    return store.put_record('science-runtime', value)
