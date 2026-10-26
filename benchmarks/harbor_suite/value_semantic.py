"""Opt-in production SemanticVerifier component comparison; no E2/E3 or admission.

Factories capture exact installed declarations/profiles in an isolated store.
Only an explicitly supplied async callback can dispatch a completion. No service,
ControlledLibrary, activation, protected gate or automatic model dispatch exists.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import time
import uuid
import asyncio
import zipfile

ASSETS = Path(__file__).with_suffix('')
REPO = Path(__file__).parents[2]
SCOPE = 'actual_semantic_verifier_component_only_not_E2_E3_admission_or_gate'


def data(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def write(path, value):
    with Path(path).open('xb') as stream:
        stream.write(data(value))


def _subjects(assets, store, *, evaluation_only=False):
    """Authored visible contradictions; no hidden-source fidelity oracle."""
    R = {'id': 'component:unopened-reference', 'sha256': 'a' * 64}
    evaluation = {'schema_version': '2.0.0', 'id': 'evaluation_verdict',
        'brief_ref': R, 'blueprint_ref': R, 'benchmark_ref': R,
        'classification': 'INCONCLUSIVE', 'aggregation_rule': 'm1_conjunctive_v1',
        'findings': [{'metric_id': 'accuracy', 'classification': 'INCONCLUSIVE', 'rule_applied': 'unmeasured',
            'rule_text': 'Unmeasured: a null baseline prevents comparison; no threshold is applied.',
            'baseline_value': None, 'treatment_value': 0.7, 'threshold': None,
            'rationale': 'Baseline is null, treatment is 0.7, threshold is null; the unmeasured rule gives INCONCLUSIVE.'}],
        'completeness': {'status': 'incomplete', 'notes': ['Baseline accuracy is unavailable.']},
        'plausibility': {'status': 'not_assessable', 'notes': ['No baseline comparison is available.']},
        'blockers': ['Baseline accuracy is unmeasured.'],
        'residual_risks': ['This synthetic verdict does not establish experimental truth.'],
        'followups': ['Consider collecting baseline evidence in separately authorized work.']}
    bad_evaluation = copy.deepcopy(evaluation); bad_evaluation['classification'] = 'PASS'
    if evaluation_only:
        return [
            ('core-semantic-01', 'evaluation', 'evaluation_verdict', evaluation,
             {'declared_output_conformance': ['PASS'], 'internal_consistency': ['PASS'], 'classification_consistent_with_findings': ['PASS'], 'finding_consistent_with_values': ['PASS']}, 'clean',
             'The visible null baseline and unmeasured finding consistently yield scientific INCONCLUSIVE; semantic consistency is PASS, not scientific acceptance.'),
            ('core-semantic-02', 'evaluation', 'evaluation_verdict', bad_evaluation,
             {'declared_output_conformance': ['PASS'], 'internal_consistency': ['FAIL'], 'classification_consistent_with_findings': ['FAIL']}, 'fault',
             'The output top-level PASS contradicts the visible INCONCLUSIVE finding and declared conjunctive aggregation rule.')]
    quote = ('The authors propose a threshold fault detector. Method: compare the threshold against an always-healthy baseline. '
             'Reported result: 70% accuracy on ten examples. Contribution: a simple demonstration. '
             'Limitations: small sample; no replication or general reliability claim.')
    paper_text = {'problem': 'The note concerns threshold-based fault detection.',
        'method': 'The authors compare a threshold with an always-healthy baseline.',
        'results': 'The authors report 70% accuracy on ten examples.',
        'contributions': 'The proposal is a simple demonstration rather than a new general algorithm.',
        'limitations': 'The sample is small and no replication establishes general reliability. Original-source equality is outside this output-only review.'}
    paper = {'schema_version': '1.0.0', 'id': 'paper_summary', 'brief_ref': R, 'documents_ref': R,
        'title': 'Qualified threshold report',
        'documents': [{'document_id': 'P1', 'source_ref': R, 'page_count': 1}],
        'citations': [{'citation_id': 'C1', 'document_id': 'P1', 'page': 1, 'start': 0, 'end': len(quote), 'quote': quote}],
        'sections': {name: {'status': 'supported', 'text': text, 'citation_ids': ['C1']} for name, text in paper_text.items()}}
    bad_paper = copy.deepcopy(paper); bad_paper['sections']['results']['citation_ids'] = ['C999']
    limits = {'time_s': 90, 'model_calls': 1, 'memory_mb': 128}
    def pin(stage):
        asset = assets[stage]; identity = store.read_record(asset['declaration_ref'])['identity']
        return {'cc_name': identity['name'], 'cc_version': identity['version_label'], 'declaration_sha256': asset['declaration_ref']['sha256']}
    nodes = [{'node_id': 'summarize', 'cc': pin('paper_summary'), 'objective': 'Produce a qualified summary.',
        'requirement_ids': ['R1'], 'deliverable_ids': [], 'predecessors': [], 'inputs': [],
        'outputs': [{'name': 'summary', 'artifact_type': 'paper_summary', 'required': True}], 'limits': limits, 'suggested_checks': []},
        {'node_id': 'deliver', 'cc': pin('paper_delivery'), 'objective': 'Render the supplied summary.',
         'requirement_ids': [], 'deliverable_ids': ['D1'], 'predecessors': ['summarize'],
         'inputs': [{'name': 'summary', 'artifact_type': 'paper_summary', 'required': True, 'source_kind': 'future_output',
                     'run_input_key': None, 'accepted_ref': None, 'future': {'producer_node': 'summarize', 'port': 'summary', 'artifact_type': 'paper_summary'}}],
         'outputs': [{'name': 'research_report', 'artifact_type': 'paper_report', 'required': True}], 'limits': limits, 'suggested_checks': []}]
    planner = {'schema_version': '3.0.0', 'id': 'component_plan', 'brief_ref': R, 'library_snapshot_ref': R,
        'resource_inventory_ref': R, 'policy_ref': R, 'plan_source': 'planned', 'nodes': nodes,
        'coverage': [{'item_id': 'R1', 'item_kind': 'requirement', 'node_ids': ['summarize']},
                     {'item_id': 'D1', 'item_kind': 'deliverable', 'node_ids': ['deliver']}],
        'topic_hints': [], 'limits': {'time_s': 180, 'model_calls': 2, 'memory_mb': 256},
        'notes': 'Advisory proposal only; references are opaque. No acceptance, resource or hidden Brief fidelity is asserted.'}
    bad_planner = copy.deepcopy(planner); bad_planner['nodes'][0]['predecessors'] = ['deliver']
    missing_planner = copy.deepcopy(planner); del missing_planner['nodes']
    packet = {'schema_version': '1.0.0', 'data': {'table': {'columns': ['v'], 'rows': [[1], [1]]},
        'calculation_result': {'arithmetic': 'decimal128_half_even', 'columns': {'v': {'count': 2, 'sum': '2'}}}},
        'files': [], 'trust': 'low', 'provenance': [R],
        'limitations': ['Only the visible packet is reviewed; no scientific validation or source preservation is established.']}
    bad_packet = copy.deepcopy(packet); bad_packet['data']['calculation_result']['columns']['v']['count'] = True
    return [
        ('evaluation-consistent-inconclusive', 'evaluation', 'evaluation_verdict', evaluation,
         {'declared_output_conformance': ['PASS'], 'internal_consistency': ['PASS'], 'classification_consistent_with_findings': ['PASS'], 'finding_consistent_with_values': ['PASS']}, 'clean',
         'A scientific INCONCLUSIVE verdict can be internally correct; it does not imply the verifier must reject the output.'),
        ('evaluation-contradiction', 'evaluation', 'evaluation_verdict', bad_evaluation,
         {'declared_output_conformance': ['PASS'], 'internal_consistency': ['FAIL'], 'classification_consistent_with_findings': ['FAIL']}, 'fault',
         'Top PASS contradicts the visible INCONCLUSIVE finding and public conjunctive rule.'),
        ('paper-visible-coherence', 'paper_summary', 'summary', paper,
         {'declared_output_conformance': ['PASS'], 'internal_consistency': ['PASS'], 'paper_citations_coherent': ['PASS']}, 'clean',
         'Visible quote and claims agree. Original PDF source fidelity is unavailable and deliberately has no truth label.'),
        ('paper-unresolved-citation', 'paper_summary', 'summary', bad_paper,
         {'declared_output_conformance': ['PASS'], 'internal_consistency': ['FAIL'], 'paper_citations_coherent': ['FAIL']}, 'fault',
         'C999 is absent from the exact visible citation index.'),
        ('planner-missing-shape', 'paper_planner', 'plan_proposal', missing_planner,
         {'declared_output_conformance': ['FAIL']}, 'fault',
         'The required nodes field is absent. Graph predicates without a supplied graph may be FAIL or INCONCLUSIVE and are not assigned a fabricated truth label.'),
        ('planner-cycle', 'paper_planner', 'plan_proposal', bad_planner,
         {'declared_output_conformance': ['PASS'], 'graph_self_consistent': ['FAIL']}, 'fault',
         'The two visible predecessor edges form a cycle.'),
        ('utility-visible-count', 'utility', 'result', packet,
         {'declared_output_conformance': ['INCONCLUSIVE'], 'internal_consistency': ['PASS'], 'limitations_consistency': ['PASS']}, 'clean',
         'Two visible rows, integer count 2 and string sum 2 agree. Exact pinned envelope conformance is INCONCLUSIVE because this actual utility profile provides a schema URN, not the complete schema bytes.'),
        ('utility-boolean-count', 'utility', 'result', bad_packet,
         {'declared_output_conformance': ['INCONCLUSIVE'], 'internal_consistency': ['FAIL'], 'limitations_consistency': ['PASS']}, 'fault',
         'True is not a count of two visible rows. Exact envelope conformance is independently INCONCLUSIVE without full pinned schema bytes in this actual utility profile.')]


def freeze(destination, *, _core_archive=None):
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.capsules.assets import build_research_assets
    from jiuwenswarm.research.capsules.paper_assets import build_paper_assets
    from jiuwenswarm.research.capsule_extensions.calculate_v2.release import prepare
    root = Path(destination); root.mkdir(parents=True, exist_ok=False)
    (root / 'public').mkdir(); (root / 'private').mkdir(); (root / 'native_skill').mkdir()
    store = SQLiteRunStore(root / 'isolated-store')
    try:
        research = build_research_assets(store)
        raw_overrides = {}; source_metadata = None
        if _core_archive is None:
            paper = build_paper_assets(store)
            assets = {'evaluation': research['evaluation'], **paper, 'utility': prepare(store)}
            subjects = _subjects(assets, store)
        else:
            from jiuwenswarm.research.compiler import prepare_compiler_assets
            compiler = asyncio.run(prepare_compiler_assets(store))
            assets = {'evaluation': research['evaluation'], 'planner': compiler['planner']}
            original, original_raw, source_metadata = _original_core_plan(_core_archive, assets['planner'], store)
            altered = copy.deepcopy(original)
            if len(altered['nodes']) < 2:
                raise ValueError('Core graph comparison requires two original nodes')
            first, second = altered['nodes'][:2]
            if first['node_id'] not in second['predecessors']:
                raise ValueError('Original graph does not contain the expected visible predecessor edge')
            first['predecessors'] = [second['node_id']]
            subjects = _subjects(assets, store, evaluation_only=True) + [
                ('core-semantic-03', 'planner', 'plan_proposal', original,
                 {'declared_output_conformance': ['PASS'], 'graph_self_consistent': ['PASS'], 'coverage_map_consistent': ['PASS']}, 'clean',
                 'Exact original core research.planner output from the supplied E1 export; visible predecessor/future graph and inverse coverage are coherent. Hidden Brief completeness, live eligibility and permissions are not truth-labeled.'),
                ('core-semantic-04', 'planner', 'plan_proposal', altered,
                 {'declared_output_conformance': ['PASS'], 'graph_self_consistent': ['FAIL']}, 'fault',
                 'One added reverse predecessor creates a visible two-node cycle while preserving the output schema and all original coverage tags.')]
            raw_overrides['core-semantic-03'] = original_raw
        manifest = []
        for case_id, role, port, output, labels, kind, rationale in subjects:
            asset = assets[role]; declaration = store.read_record(asset['declaration_ref'])
            profile = store.read_record(asset['profile_ref'])
            criteria = [row for row in profile['criteria'] if row['target_port'] in (None, port)]
            if not set(labels) <= {row['criterion_id'] for row in criteria}:
                raise ValueError('Oracle names a criterion outside the actual profile')
            output_ref = store.put_blob(raw_overrides.get(case_id, data(output)), media_type='application/json')
            context_ref = store.put_blob(data({'schema': 'semantic-component-context:1', 'case_id': case_id,
                'scope': SCOPE, 'not_a_product_review_context': True}), media_type='application/json')
            instructions = store.read_blob(profile['instruction_ref']).decode('utf-8')
            system = instructions + '\nCriteria for this output:\n' + json.dumps(criteria, ensure_ascii=False)
            payload = {'subject_declaration': store.read_blob(asset['declaration_ref']).decode('utf-8'),
                       'subject_output': store.read_blob(output_ref).decode('utf-8')}
            public = {'schema': 'ai4r-semantic-component-task:1', 'case_id': case_id, 'role': role,
                'scope': SCOPE, 'port': port, 'system': system, 'payload': payload, 'criteria': criteria,
                'declaration': declaration, 'profile': profile, 'subject_output': output,
                'response_format': {'findings': [{'criterion_id': 'each supplied criterion exactly once', 'outcome': 'PASS|FAIL|ENVIRONMENT_BLOCKED|INCONCLUSIVE', 'reason': 'nonempty visible-field evidence'}],
                    'uncertainties': [], 'limitations': [], 'required_correction': None}}
            public_sha = hashlib.sha256(data(public)).hexdigest()
            write(root / 'public' / (case_id + '.json'), public)
            (root / 'public' / (case_id + '.prompt.txt')).write_text(system + '\n\n' + json.dumps(payload, ensure_ascii=False), encoding='utf-8', newline='')
            (root / 'public' / (case_id + '.system.txt')).write_text(system, encoding='utf-8', newline='')
            write(root / 'public' / (case_id + '.payload.json'), payload)
            oracle = {'labels': labels, 'kind': kind, 'rationale': rationale,
                'oracle_scope': 'Only preselected independently obvious visible predicates; all other findings retained but ungraded.'}
            write(root / 'private' / (case_id + '.json'), oracle)
            manifest.append({'id': case_id, 'role': role, 'port': port, 'public_sha256': public_sha,
                'oracle_sha256': hashlib.sha256(data(oracle)).hexdigest(),
                'declaration_ref': asset['declaration_ref'], 'profile_ref': asset['profile_ref'],
                'instruction_ref': profile['instruction_ref'], 'output_ref': output_ref, 'context_ref': context_ref,
                'cc_identity': declaration['identity'], 'measurement_status': 'not_run'})
        (root / 'native_skill' / 'SKILL.md').write_bytes((ASSETS / 'SKILL.md').read_bytes())
        source = REPO / 'jiuwenswarm' / 'research' / 'gate.py'
        write(root / 'manifest.json', {'schema': 'ai4r-semantic-component-bank:1', 'scope': SCOPE,
            'cases': manifest, 'model_calls': 0, 'library_admission_performed': False, 'service_started': False,
            'component_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'core_PRD_subjects_only': _core_archive is not None, 'original_planner_source': source_metadata})
        if _core_archive is not None:
            cards = ['# Core semantic verification: four focused tasks', '',
                'The same production SemanticVerifier reviews research.evaluation and research.planner declarations. '
                'This is component-only, with no admission or E2/E3/full-unit claim. All outcomes are not_run until dispatch.', '']
            descriptions = [
                ('Unmeasured scientific verdict', 'Check that a properly qualified scientific INCONCLUSIVE result can satisfy semantic consistency.'),
                ('Scientific verdict aggregation', 'Check the top-level classification against the visible finding and fixed aggregation rule.'),
                ('Original core planner output', 'Check the exact original E1 core planner graph and coverage using only the declaration/output pair.'),
                ('Core planner dependency consistency', 'Check visible predecessor closure and acyclicity without assuming access to hidden Brief or catalog artifacts.')]
            for row, (name, purpose) in zip(manifest, descriptions):
                cards.extend([f"## {row['id']}: {name}", '', purpose, '',
                    f"Input: public/{row['id']}.json. Full exact system/payload prompt: public/{row['id']}.prompt.txt.", '',
                    'Grading: exact per-criterion response coverage, then independently labeled visible criteria in the separate private file. '
                    'Other findings and source-blind uncertainty remain retained and ungraded. No hidden-source truth is inferred.', ''])
            (root / 'cases.md').write_text('\n'.join(cards), encoding='utf-8')
            write(root / 'private' / 'referee-index.json', referee_index(root))
        return manifest
    finally:
        store.close()


def _original_core_plan(archive, asset, store):
    path = Path(archive)
    with zipfile.ZipFile(path) as captured:
        names = captured.namelist()
        output_paths = [name for name in names if '/planner/planner-a1/planner/outputs/' in name]
        declaration_paths = [name for name in names if name.endswith('/planner/planner-a1/planner/capsule/declaration.json')]
        if len(output_paths) != 1 or len(declaration_paths) != 1:
            raise ValueError('Need one exact original planner output and declaration in supplied export')
        raw = captured.read(output_paths[0]); original = json.loads(raw)
        declaration_bytes = captured.read(declaration_paths[0])
        if declaration_bytes != store.read_blob(asset['declaration_ref']):
            raise ValueError('Original planner declaration differs from actual installed core research.planner')
        if json.loads(declaration_bytes)['identity']['name'] != 'research.planner':
            raise ValueError('Original subject is not the core research.planner')
        contracts = [json.loads(captured.read(name)) for name in names if name.startswith('contracts/subnode-execution-contract-')]
        matches = [value for value in contracts if value.get('node_id') == 'planner' and value.get('subnode_id') == 'planner']
        if len(matches) != 1 or matches[0]['checking_profile_ref'] != asset['profile_ref']:
            raise ValueError('Original planner profile differs from the actual installed core profile')
        if matches[0]['bindings'][0]['declaration_ref'] != asset['declaration_ref']:
            raise ValueError('Original planner execution binding differs from the core declaration')
        if output_paths[0].rsplit('/', 1)[-1] != hashlib.sha256(raw).hexdigest():
            raise ValueError('Original planner output bytes differ from captured artifact hash')
    from jiuwenswarm.research.contracts import validate
    validate('plan-proposal', original)
    return original, raw, {'archive': str(path.resolve()), 'archive_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'output_path': output_paths[0], 'output_sha256': hashlib.sha256(raw).hexdigest(),
        'declaration_ref': asset['declaration_ref'], 'profile_ref': asset['profile_ref'],
        'purpose': 'Exact original core planner artifact reused as a component subject; no new full-pipeline trial is claimed.'}


def freeze_core(destination, *, planner_archive):
    """Narrow PRD-core bank: evaluation two + exact core research.planner two."""
    return freeze(destination, _core_archive=planner_archive)


def load(directory):
    root = Path(directory); manifest = json.loads((root / 'manifest.json').read_text('utf-8'))
    if manifest['schema'] != 'ai4r-semantic-component-bank:1':
        raise ValueError('Wrong component bank schema')
    cases = []
    for row in manifest['cases']:
        public = json.loads((root / 'public' / (row['id'] + '.json')).read_text('utf-8'))
        if hashlib.sha256(data(public)).hexdigest() != row['public_sha256']:
            raise ValueError('Frozen public component task changed')
        private = json.loads((root / 'private' / (row['id'] + '.json')).read_text('utf-8'))
        if hashlib.sha256(data(private)).hexdigest() != row['oracle_sha256']:
            raise ValueError('Frozen independent labels changed')
        cases.append({**row, 'public': public, 'private': private})
    return cases


def grade(case, assessment):
    findings = assessment.get('findings', [])
    outcomes = {row['criterion_id']: row['outcome'] for row in findings}
    expected = {row['criterion_id'] for row in case['public']['criteria']}
    response_valid = len(findings) == len(outcomes) and set(outcomes) == expected and all(value in {'PASS', 'FAIL', 'ENVIRONMENT_BLOCKED', 'INCONCLUSIVE'} for value in outcomes.values())
    results = [{'criterion_id': key, 'expected': allowed, 'actual': outcomes.get(key),
                'correct': outcomes.get(key) in allowed} for key, allowed in case['private']['labels'].items()]
    return {'labeled_criteria_correct': response_valid and all(row['correct'] for row in results), 'criteria': results,
            'response_valid': response_valid,
            'kind': case['private']['kind'], 'scope': 'partial_independent_visible_criterion_labels',
            'ungraded_criterion_ids': sorted(set(outcomes) - set(case['private']['labels'])),
            'original_source_truth': 'not_observable_not_scored', 'protected_gate_result': 'not_run'}


def referee_index(directory, *, actual_directory=None):
    """Private report cards; actual results are joined only from retained output.

    This object includes gold labels and must never be mounted in a reviewer
    workspace. It does not dispatch, alter observations or manufacture results.
    """
    root = Path(directory); cards = []
    for case in load(root):
        case_id = case['id']
        actual = {'status': 'not_run'}
        if actual_directory is not None:
            folder = Path(actual_directory) / case_id
            observation_path = folder / 'observation.json'
            if observation_path.is_file():
                observation = json.loads(observation_path.read_text('utf-8'))
                if observation['id'] != case_id or observation['public_sha256'] != case['public_sha256']:
                    raise ValueError('Foreign actual observation in referee index')
                actual = {'status': observation['status'], 'observation_file': str(observation_path.resolve()),
                    'grade': observation.get('grade'),
                    'raw_response_file': str((folder / 'raw-response.json').resolve()) if (folder / 'raw-response.json').is_file() else None,
                    'assembled_assessment_file': str((folder / 'assembled-assessment.json').resolve()) if (folder / 'assembled-assessment.json').is_file() else None}
        cards.append({'id': case_id, 'subject_cc': case['public']['declaration']['identity']['name'],
            'purpose': case['private']['rationale'],
            'input_file': str((root / 'public' / (case_id + '.json')).resolve()),
            'full_prompt_file': str((root / 'public' / (case_id + '.prompt.txt')).resolve()),
            'system_instruction_file': str((root / 'public' / (case_id + '.system.txt')).resolve()),
            'payload_file': str((root / 'public' / (case_id + '.payload.json')).resolve()),
            'expected_criterion_labels': case['private']['labels'], 'actual': actual,
            'grading': 'Exact response coverage, then only independently labeled visible predicates. Hidden source truth and all unlabelled findings remain ungraded.'})
    return {'schema': 'ai4r-private-semantic-referee-index:1', 'scope': SCOPE,
            'private_do_not_mount_for_reviewers': True, 'cases': cards}


async def run(directory, callback, *, case_ids=None, output=None, arm='semantic_verifier_component'):
    """Explicit callback(prompt, system=...) only; one call/output, never retry.

    callback may return the raw string or a metadata dict containing text.
    Caller owns provider authorization, model identity and shared budget.
    """
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.gate import SemanticVerifier
    root = Path(directory); selected = load(root)
    frozen_manifest = json.loads((root / 'manifest.json').read_text('utf-8'))
    source = REPO / 'jiuwenswarm' / 'research' / 'gate.py'
    if hashlib.sha256(source.read_bytes()).hexdigest() != frozen_manifest['component_source_sha256']:
        raise ValueError('Component implementation changed since freeze')
    if case_ids is not None:
        if not case_ids or len(set(case_ids)) != len(case_ids) or set(case_ids) - {c['id'] for c in selected}:
            raise ValueError('Select unique known component IDs')
        selected = [case for case in selected if case['id'] in case_ids]
    if frozen_manifest.get('core_PRD_subjects_only') and len(selected) != 1:
        raise ValueError('Select exactly one core semantic case; complete its native counterpart and grade before dispatching the next case')
    target = Path(output) if output else root / ('observations-' + uuid.uuid4().hex)
    target.mkdir(parents=True, exist_ok=False)
    store = SQLiteRunStore(root / 'isolated-store'); rows = []
    try:
        for case in selected:
            folder = target / case['id']; folder.mkdir(); calls = 0; began = time.perf_counter()
            row = {key: case[key] for key in ('id', 'role', 'public_sha256', 'declaration_ref', 'profile_ref', 'instruction_ref', 'output_ref')}
            row.update(arm=arm, scope=SCOPE, protected_gate_result='not_run', model_calls=None)
            async def invoke(prompt, *, system):
                nonlocal calls
                if calls >= 1:
                    raise RuntimeError('Component verifier call ceiling exceeded')
                if json.loads(prompt) != case['public']['payload'] or system != case['public']['system']:
                    raise ValueError('Actual verifier payload differs from frozen public task')
                write(folder / 'request.json', {'prompt': prompt, 'system': system})
                calls += 1
                result = await callback(prompt, system=system)
                write(folder / 'raw-response.json', {'result': result})
                return result['text'] if isinstance(result, dict) else result
            try:
                assessment_ref = await SemanticVerifier(store).review(case['declaration_ref'], case['output_ref'],
                    case['profile_ref'], case['context_ref'], case['port'], invoke)
                assessment = store.read_record(assessment_ref, contract_id='verifier-assessment')
                write(folder / 'assembled-assessment.json', assessment)
                row.update(status='observed', assessment_ref=assessment_ref, assessment=assessment, grade=grade(case, assessment))
            except Exception as error:
                returned = (folder / 'raw-response.json').exists()
                row.update(status='invalid_response' if returned else 'unavailable', error=type(error).__name__ + ': ' + str(error))
                if returned:
                    row['grade'] = {'response_valid': False, 'labeled_criteria_correct': False,
                                    'scope': 'returned_reply_failed_production_assessment_assembly'}
            row.update(callback_invocations=calls, elapsed_s=time.perf_counter() - began)
            write(folder / 'observation.json', row); rows.append(row)
        write(target / 'summary.json', {'scope': SCOPE, 'selected': len(selected),
            'callback_invocations': sum(row['callback_invocations'] for row in rows), 'model_calls': None,
            'model_call_accounting': 'Caller-owned provider/broker telemetry; callback invocations are not inferred model usage.',
            'observations': rows, 'automatic_retries': 0, 'labels_are_partial': True})
        return {'output': str(target.resolve()), 'rows': rows}
    finally:
        store.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--planner-archive', type=Path, required=True, help='Actual E1 originals.zip; CLI selects narrow PRD-core four only')
    args = parser.parse_args()
    print(json.dumps(freeze_core(args.output, planner_archive=args.planner_archive), indent=2))
