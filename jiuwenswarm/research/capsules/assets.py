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
STAGE_VERSIONS.update(search='m1-6', screening='m1-4', hypothesis='m1-8', builder='m1-18', benchmark='m1-10-agent-pi', evaluation='m1-5', delivery='m1-5')


def source_metadata():
    return json.loads(files('jiuwenswarm.research').joinpath('resources/capsules/stage_sources.json').read_text(encoding='utf-8'))


def load_research_catalog():
    """Installed catalog is a release input, never inferred at product startup."""
    value = json.loads(files('jiuwenswarm.research').joinpath('resources/capsules/capsule_catalog.json').read_text(encoding='utf-8'))
    if value.get('schema_version') != '1.0.0' or set(value.get('stages', {})) != set(STAGES):
        raise ResearchError('catalog_invalid', 'Installed research catalog is incomplete')
    return value


def build_research_assets(store, *, verify_catalog=True, screening_version='m1-4', delivery_version='m1-5'):
    """Return immutable candidate assets; grant no library standing or authority."""
    root = Path(__file__).parents[1]
    resources = files('jiuwenswarm.research').joinpath('resources/capsules')
    metadata = source_metadata()
    checker_files = ['checks/stages.py', 'checks/research.py', 'science.py', 'environment.py', 'target_comparisons.py']
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
        for port in declaration['ports']['inputs']:
            if port['schema_ref'] == 'urn:jiuwenswarm:m1-design:research-brief:2.0.0':
                port['schema_ref'] = 'urn:jiuwenswarm:m1-design:research-brief:3.0.0'
        identity = declaration['identity']; identity['version_label'] = STAGE_VERSIONS[stage]
        identity['summary'] = identity['summary'].replace('Synthetic declaration: ', '')
        carrier_name = ('builder_agent.py' if stage == 'builder' else
                        'benchmark_dispatch.py' if stage == 'benchmark' else stage + '.py')
        body = {carrier_name: (root / 'capsules' / carrier_name).read_bytes(),
                '_common.py': (root / 'capsules/_common.py').read_bytes()}
        metric_closure = {}
        if stage in {'hypothesis', 'builder', 'benchmark'}:
            from ..metric_contract import PROTOCOL_FILE, metric_protocol
            body['metric_contract.py'] = (root / 'metric_contract.py').read_bytes()
            body[PROTOCOL_FILE] = (root.parent / 'research_contracts' / PROTOCOL_FILE).read_bytes()
            metric_closure = {name: store.put_blob(raw, media_type='application/json' if name.endswith('.json') else 'text/x-python')
                              for name, raw in body.items() if name in {'metric_contract.py', PROTOCOL_FILE}}
            metric_closure['schemas/metric-protocol.schema.json'] = store.put_blob(
                (root.parent / 'research_contracts/schemas/metric-protocol.schema.json').read_bytes(), media_type='application/json')
            metric_closure['schemas/classification-scoring-receipt.schema.json'] = store.put_blob(
                (root.parent / 'research_contracts/schemas/classification-scoring-receipt.schema.json').read_bytes(), media_type='application/json')
            description = (' Fixed measurement protocol: ' + json.dumps(metric_protocol(), separators=(',', ':')) +
                '. Use these exact metric IDs, units, definitions, directions and physical bounds. '
                'Aggregation and Brief target_id remain separately registered. No aliases or silent renaming.')
        if stage in {'builder', 'benchmark'}:
            body['trusted_scoring.py'] = (root / 'trusted_scoring.py').read_bytes()
            if stage == 'builder':
                body['prediction_bundle.py'] = (root / 'checks/prediction_bundle.py').read_bytes()
        if stage == 'benchmark':
            for name in ('benchmark.py', 'pi_benchmark.py'):
                body[name] = (root / 'capsules' / name).read_bytes()
            for name in ('trusted_scoring.py', 'trusted_pi.py', 'pi_protocol.py', 'process_evidence.py'):
                body[name] = (root / name).read_bytes()
        if stage == 'builder':
            for name in ('builder_agent_runtime.py', 'builder_agent_service.py', 'builder_agent_host.py', 'builder_mode.py',
                         'builder_testing.py', 'process_evidence.py', 'm1_process.py', '_m1_process_child.py', 'native.py', 'pi_protocol.py', 'trusted_pi.py', 'trusted_scoring.py'):
                body[name] = (root / name).read_bytes()
        stage_runner_ref = runner_ref
        if stage == 'hypothesis':
            closure = dict(checker_closure, **metric_closure)
            closure['checks/prediction_hypothesis.py'] = store.put_blob(
                (root / 'checks/prediction_hypothesis.py').read_bytes(), media_type='text/x-python')
            stage_runner_ref = store.put_blob(json_bytes({'implementation': 'research.checks.prediction_hypothesis', 'files': closure}), media_type='application/json')
        if stage == 'builder':
            declaration['needs']['resources'] = [{'resource_key': 'poc_workspace', 'mode': 'write'}]
            declaration['needs']['network'] = {'mode': 'none', 'direction': 'none', 'allowlist': []}
            declaration['needs']['model']['tool_calling'] = False
            declaration['budget']['per_call']['tool_calls'] = 40
            declaration['budget']['per_call']['invocations'] = 20
            declaration['changes']['effect_class'] = 'compensable'
            declaration['changes']['effects'] = [row for row in declaration['changes']['effects'] if row['op'] == 'model_invoke']
            declaration['changes']['effects'].append(copy.deepcopy(metadata['benchmark']['declaration']['changes']['effects'][0]))
            identity['summary'] = 'Frozen intervention implemented through bounded native Builder actions and protected compile, unit and public smoke checks; independent gate and Benchmark retain acceptance and scoring'
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
                        'installed root scorer computes accuracy after generated-process exit against a private holdout '
                        'that is absent from model/worker/generated-code inputs and mounts. No classifier or '
                        'expected score is prescribed. It must not invoke the baseline, nest cross-role/repeat '
                        'experiments or average repeated measurements. Its visible validation path and seed '
                        'configuration must be internally consistent. Semantic review checks those visible roles '
                        'and settings under this fixed protocol; it cannot establish hidden baseline/data contents '
                        'or exact source fidelity, actual baseline-first execution or measurement correctness. '
                        'Those original identity/order/execution obligations remain protected Benchmark host checks.'
                        ' The separately registered Pi task uses approximate_pi(digits), returning exactly the truncated decimal prefix; its harness emits closed digits/decimal JSON. Private reference answers remain in root custody.')
            closure = dict(checker_closure, **metric_closure)
            for name in ('checks/builder_agent.py', 'checks/prediction_bundle.py', 'pi_protocol.py',
                         'trusted_pi.py', 'trusted_scoring.py', 'environment.py', 'process_evidence.py'):
                closure[name] = store.put_blob((root / name).read_bytes(), media_type='text/x-python')
            closure['schemas/prediction-build-receipt.v4.schema.json'] = store.put_blob((root.parent / 'research_contracts/schemas/prediction-build-receipt.v4.schema.json').read_bytes(), media_type='application/json')
            stage_runner_ref = store.put_blob(json_bytes({'implementation': 'research.checks.builder_agent', 'files': closure}), media_type='application/json')
        if stage == 'benchmark':
            declaration['needs']['resources'] = [row for row in declaration['needs']['resources'] if row['resource_key'] != 'gpu_device']
            declaration['needs']['network'] = {'mode': 'none', 'direction': 'none', 'allowlist': []}
            identity['summary'] = 'Schema-routed benchmark: classification remains the default; registered Pi requests use protected Pi scoring and baseline-first jobs'
            for port in declaration['ports']['inputs']:
                if port['name'] == 'build_receipt':
                    port['schema_ref'] = 'urn:ai4r:prediction-build-receipt:4.0.0'
            for port in declaration['ports']['outputs']:
                port['description'] = ('Schema-routed protocol, with classification as the default: generated baseline/treatment stdout contains '
                    'predictions only, never authoritative metrics. Root computes accuracy=correct_count/sample_count '
                    'after generated-process exit with private held-out labels unavailable to models, workers and generated '
                    'code. Public raw stdout refs remain the exact original predictions. Protected scoring receipt '
                    'Refs in benchmark_payload.raw_evidence_refs separately identify trusted observations and join '
                    'job/contract/sequence/role/seed/dataset/stream/scorer identities. Unmeasured jobs retain explicit '
                    'C002 reasons, not invented values. The Pi route applies only to its registered public request '
                    'schema. Host alone checks protocol registration, private scoring custody and actual execution; '
                    'output-only review checks visible fields, arithmetic and consistency.')
            closure = dict(checker_closure, **metric_closure)
            for name in ('checks/benchmark_dispatch.py', 'checks/blind_benchmark.py', 'checks/pi_benchmark.py',
                         'capsules/benchmark_dispatch.py', 'capsules/benchmark.py', 'capsules/pi_benchmark.py',
                         'trusted_scoring.py', 'trusted_pi.py', 'pi_protocol.py', 'process_evidence.py'):
                closure[name] = store.put_blob((root / name).read_bytes(), media_type='text/x-python')
            for name in ('classification-scoring-receipt.schema.json', 'prediction-build-receipt.v2.schema.json', 'prediction-build-receipt.v3.schema.json', 'prediction-build-receipt.v4.schema.json', 'pi-benchmark-payload.schema.json'):
                closure['schemas/' + name] = store.put_blob((root.parent / 'research_contracts/schemas' / name).read_bytes(), media_type='application/json')
            stage_runner_ref = store.put_blob(json_bytes({'implementation': 'research.checks.benchmark_dispatch', 'files': closure}), media_type='application/json')
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
        if stage in {'builder','benchmark'}:
            for port in declaration['ports']['outputs']:
                port['description'] += ' M1 may execute ordinary non-root processes within the app container. Network and namespaces are shared with the app; per-job cgroup isolation is not claimed. The frozen runtime and protected execution records identify the selected enforcement mode.'
        if metric_closure:
            if stage == 'builder':
                description = ' Classification tasks only:' + description + ' The separately frozen Pi task instead uses its exact declared precision and elapsed-time protocol.'
            for port in declaration['ports']['outputs']:
                port['description'] += description
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
            if stage == 'builder' and check_id == 'no_trial_no_install':
                check_id = 'bounded_development'
            target = old.get(check_id, {}).get('target', '')
            target_port = target.removeprefix('outputs.') if target.startswith('outputs.') else ports[0]
            if target_port not in ports:
                target_port = ports[0]
            if check_id.endswith('_schema') and check_id[:-7] in ports:
                target_port = check_id[:-7]
            summary = row[1][:300]
            if stage == 'benchmark' and check_id == 'network_policy_respected':
                summary = ('Execution matches its frozen mode: restricted runs prove network denial; '
                    'M1 app processes report inherited networking without claiming denial.')
            if stage == 'builder':
                summary = {
                    'bounded_development': 'Protected development tests join submitted snapshot, public inputs, bounded native action records and compile/unit/smoke evidence; no scientific acceptance authority',
                    'build_receipt_ready': 'Version 4 receipt joins the protected action journal, exact submitted snapshot, bounded model/tool/job counts and passing development checks',
                    'output_log_format': 'Static Pi output contract plus protected public smoke parsing; no scientific score accepted from generated code',
                }.get(check_id, summary)
            checks.append({'check_id': check_id, 'target_port': target_port, 'rule_summary': summary,
                           'runner_ref': stage_runner_ref, 'reads': ['output'] if check_id.endswith('_schema') else ['output', 'inputs', 'runtime_records'], 'blocking': True})
        if stage == 'benchmark':
            for key, summary in [('empirical_sequence_contiguous', 'C002: every actual receipt sequence has exactly one empirical row, contiguous from 1.'),
                                 ('empirical_values_finite', 'C002: finite metrics and missing-reason maps are disjoint and jointly cover the blueprint metric set.')]:
                checks.append({'check_id': key, 'target_port': 'benchmark_payload', 'rule_summary': summary,
                               'runner_ref': stage_runner_ref, 'reads': ['output', 'inputs', 'runtime_records'], 'blocking': True})
        if stage == 'hypothesis':
            checks.append({'check_id': 'metric_protocol_supported', 'target_port': 'blueprint',
                'rule_summary': 'Metric identities, units, measurement definitions, directions and bounds match the pinned execution protocol before Builder.',
                'runner_ref': stage_runner_ref, 'reads': ['output'], 'blocking': True})
        criteria = [{'criterion_id': key, 'question': question, 'blocking': True,
                     'answerable_from': 'declaration_and_output', 'target_port': None} for key, question in generic]
        for row in source['criteria']:
            target = row[1].strip('`') if row[1].strip('`') in ports else ports[0]
            question = row[2] if row[1].strip('`') in ports else row[1]
            criteria.append({'criterion_id': row[0].strip('`'), 'question': question,
                             'blocking': row[-1] == 'yes', 'answerable_from': 'declaration_and_output', 'target_port': target})
        if stage == 'builder':
            for criterion in criteria:
                if criterion['criterion_id'] == 'manifest_claims_no_execution':
                    criterion['criterion_id'] = 'manifest_no_unsupported_acceptance'
                    criterion['question'] = 'Does this manifest avoid unsupported scientific measurements or acceptance claims? Development tests do not establish scientific success.'
                elif criterion['criterion_id'] == 'no_embedded_results':
                    criterion['question'] = 'Does the visible code compute the declared protocol output at runtime without embedded answers, self-scoring, or unsupported scientific success claims?'
                if criterion['criterion_id'] == 'harness_orders_baseline_first':
                    criterion['question'] = ('Does the visible harness emit one closed protocol result (classification predictions or Pi digits/decimal) per default '
                        'invocation, with consistent data/seed settings and no baseline calls, repeat experiments '
                        'or averaging? Host Benchmark owns baseline-first scheduling; hidden baseline/data '
                        'fidelity and actual execution remain host checks.')
        if stage == 'benchmark':
            pi_questions = {
                'no_interpretation': 'Does this payload report measured facts and correctness checks without unsupported scientific recommendations or success claims?',
                'side_has_value_or_reason': 'For classification, does each metric side contain a value or reason? For Pi, do case runs retain explicit null timing and false correctness when unmeasured or failed?',
                'run_order_baseline_first': 'For classification, are all baseline runs first? For Pi, do five fresh baseline runs precede five treatment runs separately within each measured precision case?',
                'repeats_match_aggregate': 'Do repeats, raw elapsed values, medians and spread agree, with five repeats per measured Pi side and one per additional correctness case?',
                'delta_direction_consistent': 'For classification, is delta treatment minus baseline? For Pi, is speedup baseline median divided by treatment median at the primary 100000-place case, including values below one for slower candidates?',
            }
            for criterion in criteria:
                if criterion['criterion_id'] in pi_questions:
                    criterion['question']=pi_questions[criterion['criterion_id']]
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
    if screening_version not in {'m1-4', 'm1-5', 'm1-6'}:
        raise ResearchError('catalog_invalid', 'Unknown explicit Screening release')
    if screening_version == 'm1-5':
        result['screening'] = build_screening_asset(store, base=result['screening'], verify_catalog=verify_catalog)
    if screening_version == 'm1-6':
        result['screening'] = build_weighted_screening_asset(store, base=result['screening'], verify_catalog=verify_catalog)
    if delivery_version not in {'m1-5', 'm1-6'}:
        raise ResearchError('catalog_invalid', 'Unknown explicit Delivery release')
    if delivery_version == 'm1-6':
        result['delivery'] = build_delivery_evidence_asset(store, base=result['delivery'], verify_catalog=verify_catalog)
    return result


def build_screening_asset(store, *, base=None, verify_catalog=True):
    """Explicit additive m1-5 instruction release; preserves m1-4 and all checks.

    Capture grants no admission/activation. The campaign must select, admit and
    bind these exact immutable pins through the ordinary protected setup.
    """
    base = base or build_research_assets(store, verify_catalog=verify_catalog)['screening']
    resources = files('jiuwenswarm.research').joinpath('resources/capsules')
    declaration = copy.deepcopy(store.read_record(base['declaration_ref']))
    if declaration['identity']['version_label'] != 'm1-4':
        raise ResearchError('catalog_invalid', 'Screening m1-5 requires the exact m1-4 base release')
    body_refs = dict(base['body_refs'])
    body_refs['screening_prompt.txt'] = store.put_blob(resources.joinpath('screening_prompt_m1_5.txt').read_bytes(), media_type='text/plain')
    declaration['identity']['version_label'] = 'm1-5'
    declaration['identity']['body'] = [{'path': name, 'sha256': ref['sha256']} for name, ref in body_refs.items() if name != '_common.py']
    bundle = copy.deepcopy(store.read_record(base['bundle_ref']))
    bundle.update(id='research.screening.checks:m1-5', target_cc_version_range='m1-5.x')
    profile = copy.deepcopy(store.read_record(base['profile_ref']))
    profile.update(id='research.screening.profile:m1-5.response_contract_3',
                   target_cc_version_range='m1-5.x')
    from ..checks.schema_context import frozen_output_instructions
    instructions = resources.joinpath('verifier_implementation.txt').read_bytes()
    profile['instruction_ref'] = store.put_blob(frozen_output_instructions(instructions, declaration), media_type='text/plain')
    result = dict(base, declaration_ref=store.put_record('capsule-declaration', declaration), body_refs=body_refs,
                  bundle_ref=store.put_record('check-bundle', bundle), profile_ref=store.put_record('checking-profile', profile),
                  implementation_refs=tuple(ref for name, ref in body_refs.items() if name != '_common.py'))
    if verify_catalog:
        expected = json.loads(resources.joinpath('screening_m1_5_catalog.json').read_text(encoding='utf-8'))
        if json.loads(json_bytes(result)) != expected:
            raise ResearchError('catalog_pin_mismatch', 'Screening m1-5 differs from its explicit immutable release pin')
    return result


WEIGHTED_SCREENING_CHECKS = (
    ('screening_result_schema', 'The result, candidate set and rubric parse against their declared schemas, including bounds.'),
    ('candidate_binding', 'candidate_ref and rubric_ref equal the bound inputs.'),
    ('ids_accounted', 'Every input idea appears exactly once in scores and is either ranked or excluded with a stated violation.'),
    ('values_match_inputs', 'Each row copies the supplied assessments for the rubric weights and the idea citations exactly.'),
    ('exclusions_recomputed', 'The host recomputes every hard-constraint violation from the supplied facts; codes and eligibility must match.'),
    ('totals_recomputed', 'Each exact rational weighted total equals the sum of weight times assessment.'),
    ('ranking_recomputable', 'Ranking by exact total descending then idea_id ascending, and the Top-1, equal the exact recomputation.'),
    ('dispositions_consistent', 'Rejected, selected and eligible dispositions follow eligibility and the Top-1.'))


def build_weighted_screening_asset(store, *, base=None, verify_catalog=True):
    """Explicit additive m1-6 release: N ideas, exact rational weights, hard constraints.

    The m1-4 and m1-5 releases stay byte-identical. The input and output
    contracts are new, so this release is a standalone capability and not a
    drop-in for the fixed three-dimension pipeline. Capture grants no admission.
    """
    from ..checks.schema_context import frozen_output_instructions
    root = Path(__file__).parents[1]
    resources = files('jiuwenswarm.research').joinpath('resources/capsules')
    base = base or build_research_assets(store, verify_catalog=verify_catalog)['screening']
    declaration = copy.deepcopy(store.read_record(base['declaration_ref']))
    if declaration['identity']['version_label'] != 'm1-4':
        raise ResearchError('catalog_invalid', 'Screening m1-6 requires the exact m1-4 base release')
    sources = {'screening_weighted.py': (root / 'capsules/screening_weighted.py').read_bytes(),
               'ranking_weighted.py': (root / 'capsules/ranking_weighted.py').read_bytes(),
               'screening_weighted_prompt.txt': resources.joinpath('screening_weighted_prompt.txt').read_bytes()}
    body_refs = {'_common.py': base['body_refs']['_common.py']}
    body_refs.update({name: store.put_blob(raw, media_type='text/x-python' if name.endswith('.py') else 'text/plain')
                      for name, raw in sources.items()})
    closure = {name: store.put_blob((root / name).read_bytes(), media_type='text/x-python')
               for name in ('checks/screening_weighted.py', 'checks/research.py')}
    runner_ref = store.put_blob(json_bytes({'implementation': 'research.checks.screening_weighted', 'files': closure}),
                                media_type='application/json')
    identity = declaration['identity']
    identity['version_label'] = 'm1-6'
    identity['summary'] = ('Applies supplied hard constraints, computes exact rational weighted totals with a pure helper, '
                           'ranks deterministically, and records every one of up to 32 ideas as ranked or excluded with a reason')
    identity['carrier'] = {'ref': 'screening_weighted.py', 'sha256': body_refs['screening_weighted.py']['sha256']}
    identity['body'] = [{'path': name, 'sha256': ref['sha256']} for name, ref in body_refs.items() if name != '_common.py']
    check_ids = [key for key, _ in WEIGHTED_SCREENING_CHECKS]
    declaration['ports'] = {
        'inputs': [
            {'name': 'candidate_set', 'artifact_type': 'weighted_candidate_set', 'required': True,
             'schema_ref': 'urn:ai4r:screening-weighted-candidates:1.0.0', 'check_ids': [],
             'description': 'Up to 32 ideas with supplied exact numeric assessments and the structured facts the hard constraints use'},
            {'name': 'screening_rubric', 'artifact_type': 'weighted_rubric', 'required': True,
             'schema_ref': 'urn:ai4r:screening-weighted-rubric:1.0.0', 'check_ids': [],
             'description': 'Supplied exact rational weights, hard constraints and the deterministic tie rule'}],
        'outputs': [
            {'name': 'screening_result', 'artifact_type': 'screening_result', 'required': True,
             'schema_ref': 'urn:ai4r:screening-weighted-result:1.0.0', 'check_ids': check_ids,
             'description': 'Every idea ranked or excluded with checked violations, exact totals, the ranking and the selected idea'}]}
    declaration['guarantees']['checks'] = [
        {'id': key, 'kind': 'deterministic', 'target': 'outputs.screening_result',
         'runner': {'ref': 'protected_research_checks', 'sha256': runner_ref['sha256']},
         'anchor': 'exact output bytes and bound inputs', 'over': ['inputs_and_outputs'], 'author': 'independent check owner',
         'written_before_body': True, 'held_out': False, 'signal_source': 'captured output and bound inputs',
         'owner': 'protected profile registry', 'assurance': 'deterministic host check'} for key in check_ids]
    declaration['guarantees']['acceptance'] = list(check_ids)
    bundle = copy.deepcopy(store.read_record(base['bundle_ref']))
    bundle.update(id='research.screening.checks:m1-6', target_cc_version_range='m1-6.x',
                  checks=[{'check_id': key, 'target_port': 'screening_result', 'rule_summary': summary,
                           'runner_ref': runner_ref, 'reads': ['output'] if key.endswith('_schema') else ['output', 'inputs'],
                           'blocking': True} for key, summary in WEIGHTED_SCREENING_CHECKS])
    profile = copy.deepcopy(store.read_record(base['profile_ref']))
    profile.update(id='research.screening.profile:m1-6.response_contract_3', target_cc_version_range='m1-6.x',
                   criteria=[c for c in profile['criteria'] if c['target_port'] is None] + [
                       {'criterion_id': 'assessments_agree_with_computation', 'blocking': True,
                        'answerable_from': 'declaration_and_output', 'target_port': 'screening_result',
                        'question': "Does each idea assessment agree with the same row's violations, rank and exact total, without contradicting them?"},
                       {'criterion_id': 'opportunity_statement_grounded', 'blocking': False,
                        'answerable_from': 'declaration_and_output', 'target_port': 'screening_result',
                        'question': 'Does the opportunity statement name the selected idea and avoid claiming execution or improvement?'}])
    instructions = resources.joinpath('verifier_implementation.txt').read_bytes()
    profile['instruction_ref'] = store.put_blob(frozen_output_instructions(instructions, declaration), media_type='text/plain')
    result = dict(base, declaration_ref=store.put_record('capsule-declaration', declaration), body_refs=body_refs,
                  bundle_ref=store.put_record('check-bundle', bundle), profile_ref=store.put_record('checking-profile', profile),
                  runner_ref=runner_ref, implementation_refs=tuple(ref for name, ref in body_refs.items() if name != '_common.py'))
    if verify_catalog:
        expected = json.loads(resources.joinpath('screening_m1_6_catalog.json').read_text(encoding='utf-8'))
        if json.loads(json_bytes(result)) != expected:
            raise ResearchError('catalog_pin_mismatch', 'Screening m1-6 differs from its explicit immutable release pin')
    return result


DELIVERY_EVIDENCE_CHECKS = (
    ('research_report_schema', 'The bundle and report parse against their declared schemas: a single title line and Markdown text.'),
    ('required_sections', 'The eight declared headings appear once each, in order, each with a nonempty body.'),
    ('evidence_tables_match', 'The Results table, Run log, scope statements and counts equal the evidence bundle exactly.'),
    ('derived_values_recomputed', 'Every derived sum, mean, difference and ratio equals the exact half-up recomputation from the bundle.'),
    ('numbers_trace_to_evidence', 'Every number in the report is an evidence value or a derived value; a requested figure may appear only when declined.'))


def build_delivery_evidence_asset(store, *, base=None, verify_catalog=True):
    """Explicit additive Delivery m1-6: an evidence bundle is the typed input.

    Delivery m1-5 needs thirteen accepted pipeline artifacts and stays unchanged.
    This release takes one typed evidence bundle (request, scope statements,
    counts, measurements, run log, arithmetic policy) so a report can rest on
    supplied evidence alone. Every number must trace to the bundle. Capture grants no admission.
    """
    from ..checks.schema_context import frozen_output_instructions
    root = Path(__file__).parents[1]
    resources = files('jiuwenswarm.research').joinpath('resources/capsules')
    base = base or build_research_assets(store, verify_catalog=verify_catalog)['delivery']
    declaration = copy.deepcopy(store.read_record(base['declaration_ref']))
    if declaration['identity']['version_label'] != 'm1-5':
        raise ResearchError('catalog_invalid', 'Delivery m1-6 requires the exact m1-5 base release')
    body_refs = {'_common.py': base['body_refs']['_common.py'],
                 'delivery_evidence.py': store.put_blob((root / 'capsules/delivery_evidence.py').read_bytes(), media_type='text/x-python')}
    closure = {name: store.put_blob((root / name).read_bytes(), media_type='text/x-python')
               for name in ('checks/delivery_evidence.py', 'checks/research.py')}
    runner_ref = store.put_blob(json_bytes({'implementation': 'research.checks.delivery_evidence', 'files': closure}),
                                media_type='application/json')
    identity = declaration['identity']
    identity['version_label'] = 'm1-6'
    identity['summary'] = ('Writes a delivery report from one typed evidence bundle; the host copies the tables, recomputes '
                           'derived values and traces every reported number to the evidence')
    identity['carrier'] = {'ref': 'delivery_evidence.py', 'sha256': body_refs['delivery_evidence.py']['sha256']}
    identity['body'] = [{'path': 'delivery_evidence.py', 'sha256': body_refs['delivery_evidence.py']['sha256']}]
    check_ids = [key for key, _ in DELIVERY_EVIDENCE_CHECKS]
    declaration['ports'] = {
        'inputs': [{'name': 'evidence_bundle', 'artifact_type': 'delivery_evidence_bundle', 'required': True,
                    'schema_ref': 'urn:ai4r:delivery-evidence-bundle:1.0.0', 'check_ids': [],
                    'description': 'The request, scope statements, counts, measurements, run log and arithmetic policy the report may rest on'}],
        'outputs': [{'name': 'research_report', 'artifact_type': 'research_report', 'required': True,
                     'schema_ref': 'urn:ai4r:delivery-evidence-report:1.0.0', 'check_ids': check_ids,
                     'description': 'Actual artifact is a UTF-8 Markdown report, not a JSON object: a # title then exactly eight ## headings in the declared order'}]}
    declaration['guarantees']['checks'] = [
        {'id': key, 'kind': 'deterministic', 'target': 'outputs.research_report',
         'runner': {'ref': 'protected_research_checks', 'sha256': runner_ref['sha256']},
         'anchor': 'exact output bytes and bound inputs', 'over': ['inputs_and_outputs'], 'author': 'independent check owner',
         'written_before_body': True, 'held_out': False, 'signal_source': 'captured output and bound inputs',
         'owner': 'protected profile registry', 'assurance': 'deterministic host check'} for key in check_ids]
    declaration['guarantees']['acceptance'] = list(check_ids)
    bundle = copy.deepcopy(store.read_record(base['bundle_ref']))
    bundle.update(id='research.delivery.checks:m1-6', target_cc_version_range='m1-6',
                  checks=[{'check_id': key, 'target_port': 'research_report', 'rule_summary': summary,
                           'runner_ref': runner_ref, 'reads': ['output'] if key.endswith('_schema') else ['output', 'inputs'],
                           'blocking': True} for key, summary in DELIVERY_EVIDENCE_CHECKS])
    profile = copy.deepcopy(store.read_record(base['profile_ref']))
    profile.update(id='research.delivery.profile:m1-6.response_contract_3', target_cc_version_range='m1-6',
                   criteria=[c for c in profile['criteria'] if c['target_port'] is None] + [
                       {'criterion_id': 'unsupported_requests_declined', 'blocking': True,
                        'answerable_from': 'declaration_and_output', 'target_port': 'research_report',
                        'question': 'Does the section on requests the evidence cannot support decline every request part that the shown evidence cannot support, name the specific missing evidence, and does no other section assert that claim?'},
                       {'criterion_id': 'findings_match_tables', 'blocking': True,
                        'answerable_from': 'declaration_and_output', 'target_port': 'research_report',
                        'question': 'Do the stated findings agree with the Results and Derived comparisons tables, without attributing a value to a different workload or configuration?'},
                       {'criterion_id': 'limitations_stated', 'blocking': True,
                        'answerable_from': 'declaration_and_output', 'target_port': 'research_report',
                        'question': 'Does the report state what was not done or not measured, consistent with its scope statements?'}])
    instructions = resources.joinpath('verifier_implementation.txt').read_bytes()
    profile['instruction_ref'] = store.put_blob(frozen_output_instructions(instructions, declaration), media_type='text/plain')
    result = dict(base, declaration_ref=store.put_record('capsule-declaration', declaration), body_refs=body_refs,
                  bundle_ref=store.put_record('check-bundle', bundle), profile_ref=store.put_record('checking-profile', profile),
                  runner_ref=runner_ref, implementation_refs=tuple(ref for name, ref in body_refs.items() if name != '_common.py'))
    if verify_catalog:
        expected = json.loads(resources.joinpath('delivery_m1_6_catalog.json').read_text(encoding='utf-8'))
        if json.loads(json_bytes(result)) != expected:
            raise ResearchError('catalog_pin_mismatch', 'Delivery m1-6 differs from its explicit immutable release pin')
    return result


def build_pi_benchmark_asset(store, *, base=None, verify_catalog=True):
    """Explicit separate Pi release; default M1 consumer contracts stay intact."""
    base=base or build_research_assets(store,verify_catalog=verify_catalog)['benchmark']
    declaration=copy.deepcopy(store.read_record(base['declaration_ref']))
    declaration['identity']['version_label']='pi-m1-4'
    declaration['identity']['summary']='Frozen Pi benchmark: independent root reference, baseline-first fresh processes and protected timing'
    for port in declaration['ports']['outputs']:
        port['description'] = 'Pi benchmark output under the frozen host precision profile; baseline-first fresh processes, protected elapsed time, exact prefix correctness and retained execution evidence. This output does not use classification metrics.'
        if port['name']=='benchmark_payload':port['schema_ref']='urn:ai4r:pi-benchmark-payload:1.0.0'
    bundle=copy.deepcopy(store.read_record(base['bundle_ref']))
    bundle.update(id='research.benchmark.checks:pi-m1-4',target_cc_version_range='pi-m1-4')
    # Bundle IDs must be distinct when both versions are installed together.
    bundle['bundle_id']='research.benchmark.pi.checks'
    profile=copy.deepcopy(store.read_record(base['profile_ref']))
    profile.update(id='research.benchmark.profile:pi-m1-4',profile_id='research.benchmark.pi.profile',target_cc_version_range='pi-m1-4')
    from ..checks.schema_context import frozen_output_instructions
    instructions=files('jiuwenswarm.research').joinpath('resources/capsules/verifier_implementation.txt').read_bytes()
    profile['instruction_ref']=store.put_blob(frozen_output_instructions(instructions,declaration),media_type='text/plain')
    result=dict(base,declaration_ref=store.put_record('capsule-declaration',declaration),
                bundle_ref=store.put_record('check-bundle',bundle),profile_ref=store.put_record('checking-profile',profile))
    if verify_catalog and json.loads(json_bytes(result))!=load_research_catalog().get('protocols',{}).get('pi',{}).get('benchmark'):
        raise ResearchError('catalog_pin_mismatch','Pi Benchmark bytes differ from the explicit release pin')
    return result


def register_research_capsules(registry, check_registry, library, store, *, connectors=None, executor=None, assets=None):
    """Register only already-admitted active candidates under their exact pins."""
    from . import search, screening, hypothesis, builder_agent, benchmark_dispatch, evaluation, delivery
    from .ranking import rank_opportunities
    from ..checks.stages import ResearchChecks
    assets = assets or build_research_assets(store)
    handlers = {'search': search.execute, 'hypothesis': hypothesis.execute, 'builder': builder_agent.execute,
                'benchmark': benchmark_dispatch.execute, 'evaluation': evaluation.execute, 'delivery': delivery.execute}
    selected=list(assets.items())
    if 'benchmark' in assets and any(row['name']=='research.benchmark' and row['version']=='pi-m1-4'
           and row['standing']=='active' for row in library.entries()):
        selected.append(('benchmark',build_pi_benchmark_asset(store,base=assets['benchmark'])))
    for stage, asset in selected:
        declaration = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
        identity = declaration['identity']; entry = library.get(identity['name'], identity['version_label'])
        if entry['standing'] != 'active' or entry['declaration_ref'] != asset['declaration_ref'] or entry['body_refs'] != asset['body_refs']:
            raise ResearchError('carrier_unadmitted', 'Installed carrier is not the exact active admitted version')
        association = library.association(asset['declaration_ref'])
        if association['bundle_ref'] != asset['bundle_ref'] or association['profile_ref'] != asset['profile_ref']:
            raise ResearchError('check_pin_mismatch', 'Installed independent checks differ from admission')
        bundle = store.read_record(asset['bundle_ref'], contract_id='check-bundle')
        if stage == 'builder':
            from ..checks.builder_agent import AgentBuilderChecks
            checks = AgentBuilderChecks(stage, executor=executor)
        elif stage == 'benchmark':
            from ..checks.benchmark_dispatch import BenchmarkDispatchChecks
            checks = BenchmarkDispatchChecks(stage, executor=executor)
        elif stage == 'screening' and identity['version_label'] == 'm1-6':
            from ..checks.screening_weighted import WeightedScreeningChecks
            checks = WeightedScreeningChecks(stage, executor=executor)
        elif stage == 'delivery' and identity['version_label'] == 'm1-6':
            from ..checks.delivery_evidence import DeliveryEvidenceChecks
            checks = DeliveryEvidenceChecks(stage, executor=executor)
        else:
            checks = ResearchChecks(stage, executor=executor)
            if stage == 'hypothesis':
                from ..checks.prediction_hypothesis import PredictionHypothesisChecks
                checks = PredictionHypothesisChecks(stage, executor=executor)
        check_registry.register_bundle(bundle['bundle_id'], [check['check_id'] for check in bundle['checks']],
                                       checks, implementation_ref=asset['runner_ref'], profile_ref=asset['profile_ref'])
        if stage == 'screening' and identity['version_label'] == 'm1-6':
            from . import screening_weighted
            from .ranking_weighted import rank_weighted
            handler = screening_weighted.WeightedScreeningCarrier(rank_weighted, asset['body_refs']['ranking_weighted.py'],
                                                                  asset['body_refs']['screening_weighted_prompt.txt']).execute
        elif stage == 'delivery' and identity['version_label'] == 'm1-6':
            from . import delivery_evidence
            handler = delivery_evidence.execute
        else:
            handler = screening.ScreeningCarrier(rank_opportunities, asset['body_refs']['ranking_parent.txt'],
                                                 asset['body_refs']['screening_prompt.txt']) if stage == 'screening' else handlers[stage]
        registry.register(identity['name'], identity['version_label'], handler,
                          declaration_sha256=asset['declaration_ref']['sha256'], implementation_refs=asset['implementation_refs'])
    return assets
