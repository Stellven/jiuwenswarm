"""Job-oriented CC entry points sharing existing scoped host implementations.

Package composition changes discovery and workflow, never host authority. Only
explicit aliases are supported; callers cannot choose an arbitrary backend.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def telemetry_identity(package_id, capability):
    """Use the host's sealed bundle manifest, never hash the current source tree."""
    identity = dict(invoked_capsule=package_id, invoked_capability=capability,
                    invoked_capsule_version=None, invoked_release_sha256=None)
    try:
        bundle = Path(os.environ['CC_BUNDLE_DIR']).resolve()
        raw = (bundle.parent / 'manifest.json').read_bytes()
        manifest = json.loads(raw)
        digest = hashlib.sha256(raw).hexdigest()
        declaration = manifest['declaration']
        if (bundle.name == 'bundle' and bundle.parent.name == digest
                and manifest['format'] == 'cc-release/2' and declaration['id'] == package_id):
            identity.update(invoked_capsule_version=declaration['version'], invoked_release_sha256=digest)
    except (OSError, KeyError, ValueError, TypeError):
        pass
    return identity


def aliases(prefix, names):
    return {name: prefix + '.' + name for name in names.split()}


EVIDENCE = aliases('evidence', 'query read publish')
CYCLE = aliases('factory_loop', 'status select execute collect stop')
INTEGRATION = {
    **{'evidence_' + name: route for name, route in EVIDENCE.items()},
    **aliases('inspector', 'inspect preflight verify_effective_config inspect_strata'),
    **{'build_' + name: 'builder.' + name for name in ('submit','status','cancel','result')},
    **{'lab_' + name: 'lab.' + name for name in ('submit','status','cancel','result','ab_submit','ab_status','ab_result')},
}
ROUTES = {
    'engine.strata_throughput_workbench': {
        'inspect_evidence': 'lab_evidence.inspect',
        **aliases('throughput_workbench', 'inspect apply design verify_profile'),
        **EVIDENCE, **aliases('inference_methods', 'diagnose ablation followup test_scope propose'),
        'loop_status': 'factory_loop.status',
        **aliases('factory_loop', 'select execute collect stop'),
    },
    'factory.integration_skill': INTEGRATION,
    'engine.expert_streaming': dict(INTEGRATION, **aliases('expert_streaming','applicability engagement')),
    'factory.inference_lab': {
        'inspect_evidence': 'lab_evidence.inspect',
        **aliases('inference_methods', 'diagnose ablation followup cache_protocol propose profile_plan analyze_profile evaluate_prediction test_scope'),
        **EVIDENCE, **CYCLE,
        'apply_prefill': 'strata_prefill.apply', 'apply_drafting': 'strata_components.apply',
        'qualify_prefill': 'job_packages.qualify_profile',
        **{'lab_' + name: 'lab.' + name for name in ('submit','status','result','cancel')},
    },
    'engine.strata_prefill_workbench': {
        **aliases('prefill_workbench','inspect design apply verify_profile submit status result'),
        **EVIDENCE, **aliases('inference_methods','diagnose ablation followup test_scope'),
        **{('loop_status' if name == 'status' else name): route for name,route in CYCLE.items()},
        'qualify_profile': 'job_packages.qualify_profile',
    },
}


def qualify_profile(store, task_id, policy_id, base_profile, chunk_tokens):
    """Retain transform output, independently verify it and assess explicit policy.

    The transform is not its own verifier. A single agent capability composes
    these distinct operations and retains each receipt; no experiment is run.
    """
    from . import cc_qualification as qualification
    from .store import NotFound, encoded
    from .strata_prefill import apply
    task = store.get_task(task_id)
    configuration = task.get('constraints', {}).get('cc_qualification', {})
    if not isinstance(configuration, dict) or not isinstance(configuration.get('policies', []), list):
        raise ValueError('Invalid task qualification policy')
    policies = configuration.get('policies', [])
    if any(not isinstance(p, dict) for p in policies):
        raise ValueError('Invalid task qualification policy')
    matches = [p for p in policies if p.get('id') == policy_id]
    if len(matches) != 1:
        raise ValueError('Select exactly one existing task qualification policy')
    policy = matches[0]
    package = qualification.inspect_package(store, policy['release'])['package']
    if package['package_id'] != 'engine.strata_prefill_workbench':
        raise ValueError('Prefill qualification requires a workbench release admitted by the task')
    transformed = apply(base_profile, chunk_tokens)
    values = {'baseline_profile': base_profile, 'candidate_profile': transformed['profile']}
    identity = hashlib.sha256(encoded(dict(release=policy['release'], policy_id=policy_id, values=values)).encode()).hexdigest()
    evidence_id = 'job-prefill-profile-' + identity
    try:
        existing = store.read(task_id, evidence_id)
        if existing.get('kind') != 'prefill_profile_pair' or existing.get('values') != values:
            raise ValueError('Profile evidence identity is occupied by different evidence')
    except NotFound:
        store.append_observation(task_id, dict(obs_id=evidence_id, kind='prefill_profile_pair', values=values,
            limitations='Profile transformation output only; independent verification follows.'))
    verification = qualification.verify_unit(store, task_id, policy['release'], 'profile-single-change', evidence_id)
    assessment = qualification.assess_admission(store, task_id, policy_id, [verification['observation_id']])
    return dict(result=dict(profile=transformed['profile'], change=transformed['change'],
        profile_evidence_id=evidence_id, verification=verification, admission=assessment,
        execution_authorized=False, promotion_authorized=False, scope='bounded_configuration_invariant'))


def dispatch(store, task_id, operation, inputs):
    from .api import fields
    if operation != 'qualify_profile':
        raise ValueError('Unknown job operation')
    fields(inputs, {'policy_id','base_profile','chunk_tokens'}, {'policy_id','base_profile','chunk_tokens'})
    return qualify_profile(store, task_id, **inputs)


def main(package_id):
    """Called by a package's constant-ID wrapper under the admitted interpreter."""
    from . import telemetry
    started = time.perf_counter()
    packet, capability, route = {}, None, None
    identity = telemetry_identity(package_id, None)
    telemetry.set_turn_env()
    try:
        packet = json.load(sys.stdin)
        capability = packet['capability']
        identity = telemetry_identity(package_id, capability)
        route = ROUTES[package_id][capability]
        packet['capability'] = route
        process = subprocess.run([os.environ.get('FACTORY_PYTHON', sys.executable), '-m',
            'jiuwenswarm.factory.api', route], input=json.dumps(packet), capture_output=True,
            text=True, timeout=49, env=dict(os.environ, FACTORY_JOB_TELEMETRY=json.dumps(identity)))
        result = json.loads(process.stdout)
        if not isinstance(result, dict):
            raise ValueError('Invalid API result envelope')
        if result.get('outcome') == 'ok' and route in {'evidence.read','evidence.publish'}:
            result['outputs'] = {'record': result['outputs']}
    except subprocess.TimeoutExpired:
        result = {'outcome':'error','error':{'code':'TIMEOUT','message':'Job capability API deadline exceeded'}}
    except (ValueError, KeyError, TypeError):
        result = {'outcome':'error','error':{'code':'INVALID_INPUT','message':'Unknown package capability or invalid API packet/result'}}
    except OSError:
        result = {'outcome':'error','error':{'code':'PROCESS_FAILED','message':'Job capability API process unavailable'}}
    outputs = result.get('outputs', {})
    telemetry.emit(None, 'cc.job_call', os.environ.get('FACTORY_TASK_ID', ''), **identity,
        backend_capability=route, call_id=packet.get('call') if isinstance(packet, dict) else None,
        **telemetry.attempt_context(route, outputs),
        duration_ms=(time.perf_counter() - started) * 1000, outcome=result.get('outcome'),
        error_code=result.get('error', {}).get('code'), replay=False)
    print(json.dumps(result, allow_nan=False))
