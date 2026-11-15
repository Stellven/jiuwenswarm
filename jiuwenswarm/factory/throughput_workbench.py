"""Bounded whole-job Strata throughput configuration preparation.

Pure profile operations never admit experiments. The job package composes these
with existing evidence, methods and guarded loop facilities rather than forking
execution or weakening historical benchmark contracts.
"""
from __future__ import annotations

import copy
from .strata_components import SOURCE_REVISION, _digest, _flag, apply as _static_profile

SETTINGS = {
    'drafting': dict(location='args', key='--dspark', values=(0, 1),
        engagement='Native accepted/offered drafts and request spec agree with profile.',
        risk='Prior decode gain regressed complete512/128 throughput; free text may differ.'),
    'cpu_threads': dict(location='args', key='--cpu-threads', values=(1, 2, 4, 6, 8),
        engagement='Actual CPU expert lane worker count and nonzero CPU expert demand; source6843,6957.',
        risk='Oversubscription and CPU/GPU shared DRAM contention; explicit count disables autotuning.'),
    'engram_threads': dict(location='environment', key='DS4_ENGRAM_THREADS', values=(1, 2, 4, 8),
        engagement='Startup Engram reader thread count plus nonzero row demand; source3486,7955.',
        risk='Reader contention and numerical repeatability must be checked; Metal has a historical concurrency warning.'),
    'engram_cache_mb': dict(location='environment', key='DS4_ENGRAM_CACHE_MB', values=(0, 64, 128, 256),
        engagement='Startup row-cache capacity and request-delta hit/read counters; source3486,7955.',
        risk='Repeated identical prompts favor caching; extra memory competes with expert file pages.'),
    'ahead': dict(location='environment', key='DS4_AHEAD', values=(0, 1),
        engagement='Multiple decoded tokens and predicted/requested/hit counters; source9530,14131.',
        risk='Wrong guesses add router work and file traffic; target routing must retain all six experts.'),
    'prefill_chunk': dict(location='args', key='--prefill-chunk', values=(256, 512, 1024),
        engagement='Effective startup chunk differs and prompt length exercises it; source2793,2806.',
        risk='Prior chunk256/512 exact-output mismatch unresolved; no automatic parity qualification.'),
}


def validate_profile(profile):
    """Reuse the static full-six envelope while bounding the variable CPU field."""
    _digest(profile)
    if not isinstance(profile, dict):
        raise ValueError('Profile must be a JSON object')
    args = profile.get('args')
    if not isinstance(args, list) or not all(isinstance(v, str) for v in args):
        raise ValueError('Profile args must be strings')
    cpu, index = _flag(args, '--cpu-threads')
    if cpu not in {str(v) for v in SETTINGS['cpu_threads']['values']}:
        raise ValueError('Unsupported bounded CPU thread count')
    normalized = copy.deepcopy(profile)
    normalized['args'][index] = '8'
    drafting = _flag(args, '--dspark')[0]
    if drafting not in {'none','on'}:
        raise ValueError('Explicit dspark none/on required')
    # The source-qualified fixed budget is preserved profile context, never a
    # throughput setting. Strip only from the internal legacy validation copy;
    # the caller's profile and returned transformation retain it verbatim.
    context = normalized.get('environment', normalized.get('env'))
    if isinstance(context, dict) and 'DS4_EXPERT_BUDGET_BYTES' in context:
        if context['DS4_EXPERT_BUDGET_BYTES'] != '76000000000':
            raise ValueError('Only the admitted fixed expert budget 76000000000 is supported as profile context')
        del context['DS4_EXPERT_BUDGET_BYTES']
    _static_profile(normalized, drafting == 'on')
    if _flag(args, '--prefill-chunk')[0] not in {'256','512','1024'}:
        raise ValueError('Unsupported bounded prefill chunk')
    environment = profile.get('environment', profile.get('env'))
    for name in ('engram_threads', 'engram_cache_mb', 'ahead'):
        spec = SETTINGS[name]
        if spec['key'] in environment and environment[spec['key']] not in {str(v) for v in spec['values']}:
            raise ValueError('Unsupported bounded ' + spec['key'])
    if environment.get('DS4_ASYNC_T', '4') != '4':
        raise ValueError('Freeze DS4_ASYNC_T=4; it is a window threshold, not a thread count')
    return profile


def inspect():
    return dict(package='engine.strata_throughput_workbench', source_revision=SOURCE_REVISION,
        settings=copy.deepcopy(SETTINGS), execution_performed=False,
        scope='bounded_configuration_preparation_and_admitted_loop',
        required_evidence=['A/A repeatability', 'native mechanism engagement',
            'frozen quality gate', 'native prefill, decode and combined timing',
            'complete raw evidence and resource/cleanup receipts', 'independent winner confirmation'],
        authority='Only exact operator-admitted templates may execute; no promotion or new grants.')


def apply(base_profile, setting, value):
    if not isinstance(setting, str) or setting not in SETTINGS:
        raise ValueError('Unsupported finite throughput setting')
    spec = SETTINGS[setting]
    if type(value) is not int or value not in spec['values']:
        raise ValueError('Unsupported integer value for ' + setting)
    validate_profile(base_profile)
    result = copy.deepcopy(base_profile)
    if spec['location'] == 'args':
        before, index = _flag(result['args'], spec['key'])
        result['args'][index] = ('on' if value else 'none') if setting == 'drafting' else str(value)
        path = f'args[{index}]'
    else:
        env_key = 'environment' if 'environment' in result else 'env'
        environment = result[env_key]
        # Explicit baseline values avoid conflating a platform-dependent default
        # with the intended treatment and make the one-field comparison auditable.
        if spec['key'] not in environment:
            raise ValueError('Freeze explicit baseline ' + spec['key'] + ' before transformation')
        before = environment[spec['key']]
        environment[spec['key']] = str(value)
        path = env_key + '.' + spec['key']
    validate_profile(result)
    requested = ('on' if value else 'none') if setting == 'drafting' else str(value)
    return dict(profile=result, change=dict(setting=setting, native_setting=spec['key'],
        before=before, after=requested, changed=before != requested,
        changed_paths=[path] if before != requested else [], maximum_changed_variables=1,
        before_sha256=_digest(base_profile), after_sha256=_digest(result),
        source_revision=SOURCE_REVISION, status='candidate_profile_only',
        runtime_engagement='not_measured', required_engagement=spec['engagement'], risk=spec['risk'],
        performance_benefit='unknown', execution_authorized=False, promotion_authorized=False))


def propose(base_profile, setting, value, stage='screen'):
    if stage not in {'screen','confirm'}:
        raise ValueError('Stage must be screen or confirm')
    transformed = apply(base_profile, setting, value)
    if not transformed['change']['changed']:
        raise ValueError('Treatment must change one setting; A/A is a separately admitted control')
    return dict(kind='throughput_experiment_proposal', stage=stage,
        order=list('AB' if stage == 'screen' else 'ABBA'),
        arms={'A':copy.deepcopy(base_profile), 'B':transformed['profile']},
        change=transformed['change'], primary_metric='native_prefill_plus_decode_output_tokens_per_second',
        required_obligations=inspect()['required_evidence'], scoring_ready=False,
        requires_operator_admission=True, execution_performed=False,
        limitations=['Proposal is not an executable contract; workload, quality gate, pins, source closure, limits and deadline require a separately frozen admitted template.',
            'A one-output-token prefill screen cannot establish decode-prefetch benefit.'])


def design(store, task_id, template_id):
    """Inspect an exact operator-installed template; never generate admission."""
    import hashlib
    import json
    from pathlib import Path
    from .benchmark import validate_contract
    policy = store.get_task(task_id).get('constraints', {}).get('factory_loop', {})
    matches = [entry for entry in policy.get('templates', []) if entry.get('id') == template_id]
    if len(matches) != 1:
        raise ValueError('Select exactly one operator-installed template')
    entry = matches[0]
    raw = Path(entry['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry['sha256']:
        raise ValueError('Frozen template identity changed')
    contract = validate_contract(json.loads(raw))
    return dict(template_id=template_id, contract=contract, contract_sha256=entry['sha256'],
        execution_performed=False, promotion_authorized=False,
        authority='Installed template inspection; execute independently enforces admission and grants.')


def dispatch(store, task_id, capability, inputs):
    from .api import fields
    if capability == 'inspect':
        fields(inputs, set())
        result = inspect()
    elif capability == 'apply':
        required = {'base_profile','setting','value'}
        fields(inputs, required, required)
        result = apply(**inputs)
    elif capability == 'design':
        fields(inputs, {'template_id'}, {'template_id'})
        result = design(store, task_id, **inputs)
    elif capability == 'verify_profile':
        fields(inputs, {'base_profile','candidate_profile','setting','value'},
            {'base_profile','candidate_profile','setting','value'})
        result = apply(inputs['base_profile'], inputs['setting'], inputs['value'])
        if result['profile'] != inputs['candidate_profile']:
            raise ValueError('Candidate differs from the exact bounded single-setting transform')
        result.update(configuration_verified=True, qualification_scope='profile_pair_only')
    else:
        raise ValueError('Unknown throughput workbench capability')
    return {'result':result}
