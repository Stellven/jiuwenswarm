"""Package-bound authoring assets; capture is separate from admission/activation."""
from __future__ import annotations

import copy
import json
from importlib.resources import files
from pathlib import Path

from ..contracts import ResearchError
from ..state import json_bytes

STAGES = ('search', 'screening', 'hypothesis', 'builder', 'benchmark', 'evaluation', 'delivery')
STAGE_VERSIONS = {stage: 'm1-2-localcpu' if stage == 'benchmark' else 'm1-2' for stage in STAGES}


def source_metadata():
    return json.loads(files('jiuwenswarm.research').joinpath('resources/capsules/stage_sources.json').read_text(encoding='utf-8'))


def load_research_catalog():
    """Installed catalog is a release input, never inferred at product startup."""
    value = json.loads(files('jiuwenswarm.research').joinpath('resources/capsules/capsule_catalog.json').read_text(encoding='utf-8'))
    if value.get('schema_version') != '1.0.0' or set(value.get('stages', {})) != set(STAGES):
        raise ResearchError('catalog_invalid', 'Installed research catalog is incomplete')
    return value


def build_research_assets(store, *, verify_catalog=True):
    """Return immutable candidate assets; grant no library standing or authority."""
    root = Path(__file__).parents[1]
    resources = files('jiuwenswarm.research').joinpath('resources/capsules')
    metadata = source_metadata()
    checker_files = ['checks/stages.py', 'checks/research.py', 'science.py', 'environment.py']
    checker_closure = {name: store.put_blob((root / name).read_bytes(), media_type='text/x-python') for name in checker_files}
    runner_ref = store.put_blob(json_bytes({'implementation': 'research.checks.stages', 'files': checker_closure}), media_type='application/json')
    base_instructions = resources.joinpath('verifier_implementation.txt').read_bytes()
    from ..checks.schema_context import frozen_output_instructions
    generic = [('declared_output_conformance', 'Does this exact reviewed output conform to its corresponding declared output port and shape, without requiring sibling output ports in this single-output subject?'),
               ('internal_consistency', 'Does the output avoid contradicting itself, for example a field that disagrees with another field in the same output?'),
               ('limitations_consistency', 'Are the limitations and uncertainties the output states consistent with the output content and with the declaration\'s stated limits?')]
    result = {}
    for stage in STAGES:
        source = metadata[stage]; declaration = copy.deepcopy(source['declaration'])
        identity = declaration['identity']; identity['version_label'] = STAGE_VERSIONS[stage]
        identity['summary'] = identity['summary'].replace('Synthetic declaration: ', '')
        carrier_name = 'builder_text.py' if stage == 'builder' else stage + '.py'
        body = {carrier_name: (root / 'capsules' / carrier_name).read_bytes(),
                '_common.py': (root / 'capsules/_common.py').read_bytes()}
        stage_runner_ref = runner_ref
        if stage == 'builder':
            declaration['needs']['resources'] = []
            declaration['needs']['model']['tool_calling'] = False
            declaration['budget']['per_call']['tool_calls'] = 0
            declaration['changes']['effect_class'] = 'read_only'
            declaration['changes']['effects'] = [row for row in declaration['changes']['effects'] if row['op'] == 'model_invoke']
            identity['summary'] = 'Frozen blueprint to bounded POC file texts and mechanical archive; no tools, generated execution, installation or credential disclosure'
            closure = dict(checker_closure)
            closure['checks/builder_text.py'] = store.put_blob((root / 'checks/builder_text.py').read_bytes(), media_type='text/x-python')
            stage_runner_ref = store.put_blob(json_bytes({'implementation': 'research.checks.builder_text', 'files': closure}), media_type='application/json')
        if stage == 'benchmark':
            declaration['needs']['resources'] = [row for row in declaration['needs']['resources'] if row['resource_key'] != 'gpu_device']
            declaration['needs']['network'] = {'mode': 'none', 'direction': 'none', 'allowlist': []}
            identity['summary'] = 'Local CPU scientific benchmark: frozen offline environment, actual baseline and treatment measurements, recorded zero-GPU hardware facts'
        if stage == 'screening':
            for name in ['screening_rubric.json', 'screening_prompt.txt', 'ranking_parent.txt']:
                body[name] = resources.joinpath(name).read_bytes()
            if body['ranking_parent.txt'] != (root / 'capsules/ranking.py').read_bytes():
                raise ResearchError('helper_pin_mismatch', 'Installed pure helper differs from the packaged admitted body')
        body_refs = {name: store.put_blob(raw, media_type='application/json' if name.endswith('.json') else 'text/plain') for name, raw in body.items()}
        identity['carrier'] = {'ref': carrier_name, 'sha256': body_refs[carrier_name]['sha256']}
        identity['body'] = [{'path': name, 'sha256': ref['sha256']} for name, ref in body_refs.items() if name != '_common.py']
        declaration['needs']['external'].append({'kind': 'library', 'identifier': 'research.shared_serialization',
            'pin': {'ref': '_common.py', 'sha256': body_refs['_common.py']['sha256']}})
        # The runtime executor is a protected injected capability, not a model.
        if stage == 'benchmark':
            declaration['needs']['injects'] = []
        ports = [p['name'] for p in declaration['ports']['outputs']]
        old = {check['id']: check for check in declaration['guarantees']['checks']}
        checks = []
        for row in source['checks']:
            check_id = row[0].strip('`')
            target = old.get(check_id, {}).get('target', '')
            target_port = target.removeprefix('outputs.') if target.startswith('outputs.') else ports[0]
            if target_port not in ports:
                target_port = ports[0]
            if check_id.endswith('_schema') and check_id[:-7] in ports:
                target_port = check_id[:-7]
            checks.append({'check_id': check_id, 'target_port': target_port, 'rule_summary': row[1][:300],
                           'runner_ref': stage_runner_ref, 'reads': ['output'] if check_id.endswith('_schema') else ['output', 'inputs', 'runtime_records'], 'blocking': True})
        if stage == 'benchmark':
            for key, summary in [('empirical_sequence_contiguous', 'C002: every actual receipt sequence has exactly one empirical row, contiguous from 1.'),
                                 ('empirical_values_finite', 'C002: finite metrics and missing-reason maps are disjoint and jointly cover the blueprint metric set.')]:
                checks.append({'check_id': key, 'target_port': 'benchmark_payload', 'rule_summary': summary,
                               'runner_ref': runner_ref, 'reads': ['output', 'inputs', 'runtime_records'], 'blocking': True})
        criteria = [{'criterion_id': key, 'question': question, 'blocking': True,
                     'answerable_from': 'declaration_and_output', 'target_port': None} for key, question in generic]
        for row in source['criteria']:
            target = row[1].strip('`') if row[1].strip('`') in ports else ports[0]
            question = row[2] if row[1].strip('`') in ports else row[1]
            criteria.append({'criterion_id': row[0].strip('`'), 'question': question,
                             'blocking': row[-1] == 'yes', 'answerable_from': 'declaration_and_output', 'target_port': target})
        bundle = {'schema_version': '1.0.0', 'id': identity['name'] + '.checks:' + identity['version_label'], 'bundle_id': identity['name'] + '.checks',
                  'version': '1.0.0', 'target_cc_name': identity['name'],
                  'target_cc_version_range': identity['version_label'] + '.x' if stage == 'screening' else identity['version_label'],
                  'checks': checks, 'owner_role': 'verifier_owner'}
        instruction_ref = store.put_blob(frozen_output_instructions(base_instructions, declaration), media_type='text/plain')
        profile = {'schema_version': '1.0.0', 'id': identity['name'] + '.profile:' + identity['version_label'] + '.response_contract_3', 'profile_id': identity['name'] + '.profile',
                   'version': '1.2.0', 'target_cc_name': identity['name'],
                   'target_cc_version_range': identity['version_label'] + '.x' if stage == 'screening' else identity['version_label'],
                   'criteria': criteria, 'instruction_ref': instruction_ref, 'model_call_limit': 1, 'time_s': 180, 'owner_role': 'verifier_owner'}
        # The binder still derives mandatory checks independently. These producer
        # claims describe the same predicates; they cannot waive host additions.
        declaration['guarantees']['checks'] = []
        for check in checks:
            declaration['guarantees']['checks'].append({'id': check['check_id'], 'kind': 'deterministic',
                'target': 'outputs.' + check['target_port'], 'runner': {'ref': 'protected_research_checks', 'sha256': stage_runner_ref['sha256']},
                'anchor': 'exact output bytes and protected run records', 'over': ['outputs'], 'author': 'independent check owner',
                'written_before_body': True, 'held_out': False, 'signal_source': 'captured output and run records',
                'owner': 'protected profile registry', 'assurance': 'deterministic host check'})
        declaration['guarantees']['acceptance'] = [check['check_id'] for check in checks]
        bundle_ref = store.put_record('check-bundle', bundle)
        profile_ref = store.put_record('checking-profile', profile)
        declaration_ref = store.put_record('capsule-declaration', declaration)
        result[stage] = {'declaration_ref': declaration_ref, 'body_refs': body_refs,
                         'bundle_ref': bundle_ref, 'profile_ref': profile_ref, 'runner_ref': stage_runner_ref,
                         'implementation_refs': tuple(ref for name, ref in body_refs.items() if name != '_common.py'),
                         'source_receipt': source['source']}
    if verify_catalog:
        expected = load_research_catalog()['stages']
        # JSON round trip makes tuple/list representation immaterial; exact
        # identities, all implementation bytes and independent assets stay fixed.
        if json.loads(json_bytes(result)) != expected:
            raise ResearchError('catalog_pin_mismatch', 'Installed research bytes differ from the frozen release catalog')
    return result


def register_research_capsules(registry, check_registry, library, store, *, connectors=None, executor=None, assets=None):
    """Register only already-admitted active candidates under their exact pins."""
    from . import search, screening, hypothesis, builder_text, benchmark, evaluation, delivery
    from .ranking import rank_opportunities
    from ..checks.stages import ResearchChecks
    assets = assets or build_research_assets(store)
    handlers = {'search': search.execute, 'hypothesis': hypothesis.execute, 'builder': builder_text.execute,
                'benchmark': benchmark.execute, 'evaluation': evaluation.execute, 'delivery': delivery.execute}
    for stage, asset in assets.items():
        declaration = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
        identity = declaration['identity']; entry = library.get(identity['name'], identity['version_label'])
        if entry['standing'] != 'active' or entry['declaration_ref'] != asset['declaration_ref'] or entry['body_refs'] != asset['body_refs']:
            raise ResearchError('carrier_unadmitted', 'Installed carrier is not the exact active admitted version')
        association = library.association(asset['declaration_ref'])
        if association['bundle_ref'] != asset['bundle_ref'] or association['profile_ref'] != asset['profile_ref']:
            raise ResearchError('check_pin_mismatch', 'Installed independent checks differ from admission')
        bundle = store.read_record(asset['bundle_ref'], contract_id='check-bundle')
        if stage == 'builder':
            from ..checks.builder_text import TextBuilderChecks
            checks = TextBuilderChecks(stage, executor=executor)
        else:
            checks = ResearchChecks(stage, executor=executor)
        check_registry.register_bundle(bundle['bundle_id'], [check['check_id'] for check in bundle['checks']],
                                       checks, implementation_ref=asset['runner_ref'], profile_ref=asset['profile_ref'])
        handler = screening.ScreeningCarrier(rank_opportunities, asset['body_refs']['ranking_parent.txt'],
                                             asset['body_refs']['screening_prompt.txt']) if stage == 'screening' else handlers[stage]
        registry.register(identity['name'], identity['version_label'], handler,
                          declaration_sha256=asset['declaration_ref']['sha256'], implementation_refs=asset['implementation_refs'])
    return assets
