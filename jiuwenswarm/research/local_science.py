"""Explicit external public data and independently scored runtime capture.

No dataset, solution or expected score is supplied by this module. Private
holdout bytes are never captured as agent-readable artifacts.
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
print(json.dumps({'predictions': [{'id': row['id'], 'label': majority} for row in data['test']]}))
'''

SAMPLE_REQUEST = (
    'Using the externally supplied classification training data, choose and justify one bounded '
    'classifier improvement over the captured majority-class baseline. '
    'Preserve the training data, test population, label vocabulary and trusted accuracy scoring. '
    'Use only the Python standard library, no network or GPU. Metric accuracy (fraction), higher is better; '
    'success if treatment accuracy > baseline accuracy, falsification if treatment accuracy <= baseline accuracy. '
    'Produce predictions only; hidden test labels are available solely to the trusted host scorer. '
    'Run the baseline first then the treatment, 3 repeats each, fixed execution seed 42. '
    'Deliver genuine measured results, POC files, raw logs, uncertainty and limitations, '
    'including a negative or inconclusive result if the improvement does not succeed.')


def capture_local_science_resources(store, *, public_path, scoring_pins):
    """Capture an explicitly supplied public package; never create example data."""
    from .trusted_scoring import parse_public_dataset
    source = Path(public_path)
    if (not source.is_absolute() or source.is_symlink() or not source.is_file()
            or source.stat().st_size > 2 * 1024 * 1024):
        raise ResearchError('external_dataset_invalid', 'An explicit bounded public data.json is required')
    data = source.read_bytes()
    parse_public_dataset(data)
    expected_pins = {'holdout_sha256', 'scorer_sha256'}
    if (type(scoring_pins) is not dict or set(scoring_pins) != expected_pins
            or any(type(value) is not str or len(value) != 64
                   or any(c not in '0123456789abcdef' for c in value) for value in scoring_pins.values())):
        raise ResearchError('external_scoring_invalid', 'Protected external scoring commitments are required')
    requirements = store.put_blob(b'', media_type='text/plain')
    approval = store.put_blob(json_bytes({'schema': 'ai4r-local-environment-approval:1',
        'purpose': 'Externally supplied classification; Python standard library only; no third-party packages',
        'platform_fact': [platform.system(), platform.machine(), platform.python_version()]}), media_type='application/json')
    lock = {'schema_version': '1.0.0', 'id': 'external_classification_stdlib_environment',
        'platform': platform.system().lower() + '-' + platform.machine().lower(),
        'requirements_ref': requirements, 'package_refs': [], 'approval_ref': approval}
    validate('environment-lock', lock)
    lock_ref = store.put_record('environment-lock', lock)
    guide = b'''# Externally supplied classification project

Public data.json contains dataset_id, feature_names, classes, labelled train rows
and unlabelled test rows. Each row has an opaque id and a finite numeric features
array. Only train rows have label. Test labels and the generation seed are private
to an independent evaluator and are unavailable to model or generated code.
Choose and justify a classifier using the supplied training data. Keep the captured
majority-class baseline and public data unchanged. Implement predict(train, test)
in poc_patch.py, returning one declared string label per test row in test order.
run_benchmark.py reads /resources/validation/data.json and prints exactly one JSON
object: {"predictions": [{"id": "<test row id>", "label": "<declared class>"}]}.
It must cover every test id exactly once and must not emit metrics or accuracy.
The trusted host scores successful predictions after the sandbox has stopped.
Use only the Python standard library, no network, GPU or external data. Baseline
runs precede treatment runs, three repeats each, fixed execution seed 42. Accuracy
is the fraction of correct predictions. Improvement succeeds only if treatment
accuracy exceeds baseline accuracy; equality or lower falsifies the claim.
Preserve negative and inconclusive outcomes and report uncertainty and limitations.
'''
    def snapshot(key, kind, names):
        value = {'schema_version': '1.0.0', 'id': key, 'kind': kind,
            'origin': 'Explicitly imported external public classification package',
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
    scoring_profile = {'protocol': 'ai4r-blind-classification:1', 'public_dataset_ref': validation,
        'public_file': 'data.json', 'public_data_sha256': hashlib.sha256(data).hexdigest(),
        'holdout_path': '/run/ai4r-private-qa/holdout.json', **scoring_pins, 'max_stdout_bytes': 8388608}
    return {'resource_inventory_ref': store.put_record('resource-inventory', inventory),
        'run_inputs': {'baseline_resource': baseline, 'validation_resource': validation},
        'host_records': {'environment_lock': lock_ref},
        'resource_reads': [ref for _, _, ref in rows],
        'approved_environments': [{'lock_ref': lock_ref, 'approval_ref': approval,
            'platform_fact': [platform.system(), platform.machine(), platform.python_version()], 'wheel_filenames': {}}],
        'guide': guide.decode('utf-8'), 'guide_ref': guide_ref, 'local_example_ref': None,
        'scoring_profile': scoring_profile}


def capture_local_science_runtime(store, *, configuration_ref, policy_ref, resource_inventory_ref,
                                  entries, approved_environments, scoring_profile=None):
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
                if declaration['identity']['name'] == 'research.benchmark' else (['builder_action'] if declaration['identity']['version_label'] in {'m1-14','m1-15','m1-16','m1-17','m1-18'} else ['builder_test'] if declaration['identity']['carrier']['ref'] == 'builder_loop.py' else ['collect_builder'])})
    value = {'schema': 'ai4r-science-runtime:2',
        'build_id': verify_installed_build(), 'gpu_required': False,
        'profile': {'asset_root': '/var/lib/ai4r-executor/assets',
            'environment_root': '/var/lib/ai4r-executor/environments', 'memory_mb': 1024, 'pids_max': 64,
            'run_timeout_s': 60, 'provision_timeout_s': 60, 'baseline_arguments': [], 'treatment_arguments': [],
            'uv_path': '/usr/local/bin/uv', 'python_path': sys._base_executable},
        'approved_environments': approved_environments, 'execution_bindings': bindings}
    if scoring_profile is not None:
        value.update(schema='ai4r-science-runtime:4' if scoring_profile.get('protocol') == 'ai4r-pi:1' else 'ai4r-science-runtime:3', scoring_profile=scoring_profile)
    mode = os.environ.get('AI4R_EXECUTION_MODE', 'restricted')
    if mode not in {'restricted','m1_app_process'}:
        raise ResearchError('configuration','Unsupported scientific execution mode')
    if mode == 'm1_app_process':
        value.update(schema='ai4r-science-runtime:5',execution_mode=mode,scoring_profile=scoring_profile)
    # One installed build can legitimately capture distinct protected operator
    # configurations. Name the exact frozen context/body, preserving old records
    # and idempotence without reusing a build-only ID for different bytes.
    identity = {'configuration_ref': configuration_ref, 'policy_ref': policy_ref,
                'resource_inventory_ref': resource_inventory_ref, 'runtime': value}
    value['id'] = 'local-cpu-science-' + hashlib.sha256(json_bytes(identity)).hexdigest()
    from .science_runtime import decode_science_runtime_record
    decode_science_runtime_record(value)
    # The private schema is validated by the decoder above. ``science-runtime``
    # is the protected capture kind consumed by the broker, not a public schema
    # alias understood by put_record().
    return store.append_record('science-runtime', value)
