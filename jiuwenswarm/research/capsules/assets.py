"""Package-bound authoring assets; capture is separate from admission/activation."""
from __future__ import annotations

import copy
import json
from importlib.resources import files
from pathlib import Path

from ..contracts import ResearchError
from ..state import json_bytes

STAGES = ('search', 'screening', 'hypothesis', 'builder', 'benchmark', 'evaluation', 'delivery')
STAGE_VERSIONS = {stage: 'm1-3' for stage in STAGES}
STAGE_VERSIONS.update(search='m1-5', hypothesis='m1-5', builder='m1-11', benchmark='m1-4-blindcpu', evaluation='m1-4', delivery='m1-4')


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
        if stage in {'builder', 'benchmark'}:
            body['trusted_scoring.py'] = (root / 'trusted_scoring.py').read_bytes()
            if stage == 'builder':
                body['prediction_bundle.py'] = (root / 'checks/prediction_bundle.py').read_bytes()
        stage_runner_ref = runner_ref
        if stage == 'builder':
            declaration['needs']['resources'] = []
            declaration['needs']['model']['tool_calling'] = False
            declaration['budget']['per_call']['tool_calls'] = 0
            declaration['changes']['effect_class'] = 'read_only'
            declaration['changes']['effects'] = [row for row in declaration['changes']['effects'] if row['op'] == 'model_invoke']
            identity['summary'] = 'Frozen blueprint to bounded POC file texts and mechanical archive; no tools, generated execution, installation or credential disclosure'
            for port in declaration['ports']['outputs']:
                if port['name'] == 'bundle':
                    port['description'] = ('Actual artifact is a ZIP archive, not a JSON object. The referenced bundle schema '
                        'describes its logical parts: archive_format denotes ZIP, entry_names denotes its root file paths, '
                        'and requirements_txt, poc_patch_py and run_benchmark_py denote the contents of requirements.txt, '
                        'poc_patch.py and run_benchmark.py respectively. For text-only semantic review the host supplies '
                        'the fixed archive projection: each entry has path, sha256, size and its exact UTF-8 content block. '
                        'Map those displayed paths and content blocks to the logical schema parts; a JSON wrapper with '
                        'those logical field names is not required in the ZIP or its projection. Assess the shown archive '
                        'members and code contents under the declared constraints; do not execute or retrieve anything. '
                        'The fixed execution protocol keeps captured baseline and validation resources read-only. '
                        'Protected Benchmark runs the unchanged captured baseline command once per baseline job, '
                        'completes all registered baseline repeats, then invokes run_benchmark.py once per treatment '
                        'job and aggregates the actual receipts. Accordingly, run_benchmark.py is a one-job treatment '
                        'harness: its default invocation calls predict(train,test) once and emits exactly '
                        '{"predictions":[{"id":"test ID","label":"declared string class"}]} with all test IDs '
                        'once. The patch returns string labels aligned with the test rows. Public data.json '
                        'contains feature_names, classes, labeled train rows and unlabeled test feature rows; '
                        'it contains no held-out labels. Generated code emits no metrics or accuracy; a separately '
                        'installed root scorer computes accuracy after sandbox exit against a private holdout '
                        'that is absent from model/worker/generated-code inputs and mounts. No classifier or '
                        'expected score is prescribed. It must not invoke the baseline, nest cross-role/repeat '
                        'experiments or average repeated measurements. Its visible validation path and seed '
                        'configuration must be internally consistent. Semantic review checks those visible roles '
                        'and settings under this fixed protocol; it cannot establish hidden baseline/data contents '
                        'or exact source fidelity, actual baseline-first execution or measurement correctness. '
                        'Those original identity/order/execution obligations remain protected Benchmark host checks.')
            closure = dict(checker_closure)
            closure['checks/builder_text.py'] = store.put_blob((root / 'checks/builder_text.py').read_bytes(), media_type='text/x-python')
            closure['checks/prediction_bundle.py'] = store.put_blob((root / 'checks/prediction_bundle.py').read_bytes(), media_type='text/x-python')
            closure['trusted_scoring.py'] = store.put_blob((root / 'trusted_scoring.py').read_bytes(), media_type='text/x-python')
            closure['schemas/prediction-build-receipt.v2.schema.json'] = store.put_blob((root.parent / 'research_contracts/schemas/prediction-build-receipt.v2.schema.json').read_bytes(), media_type='application/json')
            stage_runner_ref = store.put_blob(json_bytes({'implementation': 'research.checks.builder_text', 'files': closure}), media_type='application/json')
        if stage == 'benchmark':
            declaration['needs']['resources'] = [row for row in declaration['needs']['resources'] if row['resource_key'] != 'gpu_device']
            declaration['needs']['network'] = {'mode': 'none', 'direction': 'none', 'allowlist': []}
            identity['summary'] = 'Blind CPU classification benchmark: raw predictions, root-only held-out scoring, actual baseline-first jobs and protected scoring receipts'
            for port in declaration['ports']['inputs']:
                if port['name'] == 'build_receipt':
                    port['schema_ref'] = 'urn:ai4r:prediction-build-receipt:2.0.0'
            for port in declaration['ports']['outputs']:
                port['description'] = ('Blind classification protocol: generated baseline/treatment stdout contains '
                    'predictions only, never authoritative metrics. Root computes accuracy=correct_count/sample_count '
                    'after sandbox exit with private held-out labels unavailable to models, workers and generated '
                    'code. Public raw stdout refs remain the exact original predictions. Protected scoring receipt '
                    'Refs in benchmark_payload.raw_evidence_refs separately identify trusted observations and join '
                    'job/contract/sequence/role/seed/dataset/stream/scorer identities. Unmeasured jobs retain explicit '
                    'C002 reasons, not invented values. Host alone checks private scoring custody and actual '
                    'execution; output-only semantic review checks visible fields, arithmetic and consistency.')
            closure = dict(checker_closure)
            for name in ('checks/blind_benchmark.py', 'trusted_scoring.py'):
                closure[name] = store.put_blob((root / name).read_bytes(), media_type='text/x-python')
            for name in ('classification-scoring-receipt.schema.json', 'prediction-build-receipt.v2.schema.json'):
                closure['schemas/' + name] = store.put_blob((root.parent / 'research_contracts/schemas' / name).read_bytes(), media_type='application/json')
            stage_runner_ref = store.put_blob(json_bytes({'implementation': 'research.checks.blind_benchmark', 'files': closure}), media_type='application/json')
        if stage == 'evaluation':
            for port in declaration['ports']['outputs']:
                if port['name'] == 'evaluation_verdict':
                    port['description'] = ('Scientific verdict JSON. Fixed public aggregation_rule m1_conjunctive_v1 '
                        'combines the listed finding classifications and plausibility.status by first match: '
                        '(1) plausibility implausible gives INCONCLUSIVE; (2) otherwise any FAIL finding gives FAIL; '
                        '(3) otherwise any INCONCLUSIVE finding gives INCONCLUSIVE; (4) otherwise any '
                        'CONDITIONALLY_ACCEPTABLE finding gives CONDITIONALLY_ACCEPTABLE; (5) otherwise all findings '
                        'PASS gives PASS. Plausibility plausible or not_assessable adds no separate override. '
                        'Per metric, a null baseline or treatment value means INCONCLUSIVE with rule_applied '
                        'unmeasured; success means PASS, falsification FAIL, registered conditional means '
                        'CONDITIONALLY_ACCEPTABLE, and unresolved middle means INCONCLUSIVE. Findings state the '
                        'applied rule_text, values and threshold. Completeness is incomplete exactly when a '
                        'finding is unmeasured; blockers is nonempty exactly when a finding is unmeasured or '
                        'plausibility is implausible. Residual risks may remain under a scientific PASS. These '
                        'are fixed source semantics, not permission to alter thresholds or infer unseen inputs. '
                        'Output-only review checks the shown findings/rules/values and aggregation consistency; '
                        'protected host checks independently establish exact source bindings and recomputation. '
                        'A scientific classification does not itself authorize application acceptance or execution.')
        if stage == 'delivery':
            for port in declaration['ports']['outputs']:
                if port['name'] == 'research_report':
                    port['description'] = ('Actual artifact is a UTF-8 Markdown report, not a JSON object. The logical '
                        'research-report schema sections string denotes the complete decoded Markdown content shown as '
                        'subject_output; no JSON wrapper or literal sections field is required in the report. The content '
                        'still requires a # title followed by exactly nine nonempty ## headings, in this order: '
                        '1. Objective; 2. Opportunity and citations; 3. Hypothesis and registered criteria; '
                        '4. Method and POC; 5. Results: baseline vs treatment; 6. Scientific verdict and reasoning; '
                        '7. Limitations and risks; 8. Follow-up recommendations; 9. Reproducibility. '
                        'Assess this shown Markdown under all declared report constraints and criteria; no source lookup '
                        'or execution is available. The separate delivery_manifest output remains JSON.')
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
                               'runner_ref': stage_runner_ref, 'reads': ['output', 'inputs', 'runtime_records'], 'blocking': True})
        criteria = [{'criterion_id': key, 'question': question, 'blocking': True,
                     'answerable_from': 'declaration_and_output', 'target_port': None} for key, question in generic]
        for row in source['criteria']:
            target = row[1].strip('`') if row[1].strip('`') in ports else ports[0]
            question = row[2] if row[1].strip('`') in ports else row[1]
            criteria.append({'criterion_id': row[0].strip('`'), 'question': question,
                             'blocking': row[-1] == 'yes', 'answerable_from': 'declaration_and_output', 'target_port': target})
        if stage == 'builder':
            for criterion in criteria:
                if criterion['criterion_id'] == 'harness_orders_baseline_first':
                    criterion['question'] = ('Does the visible harness emit one batch of ID/string-label predictions per default '
                        'invocation, with consistent data/seed settings and no baseline calls, repeat experiments '
                        'or averaging? Host Benchmark owns baseline-first scheduling; hidden baseline/data '
                        'fidelity and actual execution remain host checks.')
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
        elif stage == 'benchmark':
            from ..checks.blind_benchmark import BlindBenchmarkChecks
            checks = BlindBenchmarkChecks(stage, executor=executor)
        else:
            checks = ResearchChecks(stage, executor=executor)
        check_registry.register_bundle(bundle['bundle_id'], [check['check_id'] for check in bundle['checks']],
                                       checks, implementation_ref=asset['runner_ref'], profile_ref=asset['profile_ref'])
        handler = screening.ScreeningCarrier(rank_opportunities, asset['body_refs']['ranking_parent.txt'],
                                             asset['body_refs']['screening_prompt.txt']) if stage == 'screening' else handlers[stage]
        registry.register(identity['name'], identity['version_label'], handler,
                          declaration_sha256=asset['declaration_ref']['sha256'], implementation_refs=asset['implementation_refs'])
    return assets
