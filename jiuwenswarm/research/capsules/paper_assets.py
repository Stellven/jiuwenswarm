"""Additive immutable PDF summary release, separate from all scientific POC pins."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from ..contracts import ResearchError
from ..state import json_bytes
from ..summary_planning import PAPER_PLANNER_VERSION
from ..checks.schema_context import frozen_output_instructions
from ..checks.paper import SUMMARY_CHECKS, DELIVERY_CHECKS
from .paper_summary import SUMMARY, BUFFER
from .paper_delivery import REPORT, MANIFEST

VERSION = 'paper-m1-5'
NAMES = {'paper_summary': 'research.paper_summary', 'paper_delivery': 'research.paper_summary_delivery',
         'paper_planner': 'workflow.paper_planner'}


def _port(name, kind, schema, description):
    return {'name': name, 'artifact_type': kind, 'schema_ref': schema, 'required': True,
            'check_ids': [], 'description': description}


def build_paper_assets(store, *, verify_catalog=True):
    root = Path(__file__).parents[1]
    assets = root.parent / 'research_assets'
    base = json.loads((assets / 'compiler/requirements.declaration.json').read_text('utf-8'))
    planner = json.loads((assets / 'planner/planner.declaration.json').read_text('utf-8'))
    generic = [
        ('declared_output_conformance', 'Does this exact output conform to the declared type, fields and shape?'),
        ('internal_consistency', 'Do output fields and local ID references agree internally?'),
        ('limitations_consistency', 'Are stated uncertainties and limitations coherent with the output?')]
    summary_questions = [
        ('paper_sections_complete', 'Are all five distinct sections problem, method, results, contributions and limitations nonempty, with an explicit not-stated status when information is absent?'),
        ('paper_claims_qualified', 'Does the summary distinguish reported findings, author claims and missing information, preserving visible numbers, units and qualifications without claiming new execution?'),
        ('paper_citations_coherent', 'Do supported sections cite existing citation IDs with visible document/page/exact quote entries that plausibly substantiate the associated claims, without internally contradictory quote use? Source-file equality is a protected host check, not available to this reviewer.'),
        ('paper_synthesis_readable', 'Is the synthesis specific, readable and coherent, with distinct sections and useful scientific detail rather than generic filler?')]
    delivery_questions = [
        ('paper_delivery_sections', 'For the Markdown report, are the title and all five nonempty headings present? For the JSON manifest, are report, brief, summary, source and gate files coherently represented?'),
        ('paper_delivery_citations', 'For the report, are the sources represented by concise readable PDF/page citations without raw extracted quotation blocks? For the manifest, is the accepted structured summary evidence file listed with internally consistent source references and source file entries?'),
        ('paper_delivery_honesty', 'Does the output present a paper summary without claiming a new benchmark, experiment, scientific acceptance or unseen source inspection?'),
        ('paper_delivery_usable', 'Is the report readable and organized, or is this manifest an unambiguous, safe relative-path file inventory with no missing_evidence?')]
    base_review = (root / 'resources/capsules/verifier_implementation.txt').read_bytes()
    closure_names = ('checks/paper.py', 'capsules/paper_summary.py', 'capsules/paper_delivery.py', 'run_inputs.py')
    closure = {name: store.put_blob((root / name).read_bytes(), media_type='text/x-python') for name in closure_names}
    for name in ('paper-summary', 'paper-report', 'paper-delivery-manifest', 'paper-document-buffer'):
        closure['schemas/' + name + '.schema.json'] = store.put_blob(
            (root.parent / 'research_contracts/schemas' / (name + '.schema.json')).read_bytes(), media_type='application/json')
    runner_ref = store.put_blob(json_bytes({'implementation': 'research.checks.paper', 'files': closure}), media_type='application/json')
    result = {}
    for stage in NAMES:
        release = PAPER_PLANNER_VERSION if stage == 'paper_planner' else VERSION
        declaration = copy.deepcopy(planner if stage == 'paper_planner' else base)
        identity = declaration['identity']
        identity.update(name=NAMES[stage], version_label=release,
            summary={'paper_summary': 'Summarize canonical PDF pages with exact source quotations and page coordinates',
                     'paper_delivery': 'Render accepted paper summary into Markdown and an exact evidence manifest',
                     'paper_planner': 'Propose exactly the protected two-node PDF summary workflow'}[stage])
        body_names = ['capsules/' + stage + '.py', 'capsules/_common.py']
        if stage == 'paper_delivery':
            body_names.append('capsules/paper_summary.py')
        if stage == 'paper_planner':
            body_names.extend(('summary_planning.py', 'unified_planning.py'))
        body_refs = {name: store.put_blob((root / name).read_bytes(), media_type='text/x-python') for name in body_names}
        carrier = 'capsules/' + stage + '.py'
        identity['carrier'] = {'ref': carrier, 'sha256': body_refs[carrier]['sha256']}
        identity['body'] = [{'path': name, 'sha256': ref['sha256']} for name, ref in body_refs.items() if name != 'capsules/_common.py']
        declaration['needs']['external'] = [{'kind': 'library', 'identifier': 'research.shared_serialization',
            'pin': {'ref': 'capsules/_common.py', 'sha256': body_refs['capsules/_common.py']['sha256']}}]
        declaration['needs']['resources'] = []
        declaration['coverage']['undeclared_notes'] = ['Output-only semantic review cannot inspect external source contents; protected host checks establish source identity and exact citation spans.']
        declaration['guarantees']['unanchored'] = ['Semantic fidelity remains subject to independent output-only assessment and exact source-citation host checks; no new experiment is performed.']
        declaration['budget']['per_call']['wall_s'] = 180 if stage == 'paper_summary' else 120
        if stage == 'paper_summary':
            declaration['needs']['resources'] = [{'resource_key': 'local_document_buffer', 'mode': 'read'}]
            declaration['ports'] = {'inputs': [
                _port('brief', 'research_brief', 'urn:jiuwenswarm:m1-design:research-brief:3.0.0', 'Accepted governing Brief'),
                _port('documents', 'local_document_buffer', BUFFER, 'Exact current-run qualified canonical PDF text buffer; form-feed separates original pages')],
                'outputs': [_port('summary', 'paper_summary', SUMMARY,
                    'Structured paper summary. Five sections use supported or not_stated status. Supported sections cite exact original text quotations, with P1 document IDs, one-based PDF pages and zero-based Unicode global half-open start/end coordinates. The complete canonical PDF text is provided as bounded contiguous source chunks with stable evidence IDs and exact page/offset metadata. Model selects supplied evidence IDs separately for each section and authors the synthesis. Carrier copies the selected original chunks without alteration and mechanically assigns shared citation IDs/index from those section assignments before publication. It never repairs or searches approximately for an authored quote. Source equality is checked by host, not inferred by blind review.')]}
            keys, questions = SUMMARY_CHECKS, summary_questions
        elif stage == 'paper_delivery':
            declaration['identity']['kind'] = 'tool'
            declaration['needs']['injects'] = []
            declaration['changes']['effects'] = []
            declaration['ports'] = {'inputs': [
                _port('brief', 'research_brief', 'urn:jiuwenswarm:m1-design:research-brief:3.0.0', 'Accepted governing Brief'),
                _port('summary', 'paper_summary', SUMMARY, 'Exact current-run accepted summary'),
                _port('gate_decision_index', 'gate_decision_index', 'gate-decision-index:field-contract:1', 'Protected accepted predecessor gate index')],
                'outputs': [_port('research_report', 'paper_report', REPORT,
                    'Actual UTF-8 Markdown decoded text, not a JSON wrapper. A # title followed by exactly five nonempty ## headings Problem, Method, Results, Contributions, Limitations. All accepted summary prose is rendered unchanged, followed within each supported section by one concise Sources line of deduplicated readable [PDF 1, p. 2] page citations. No raw extracted source quotation blocks or internal citation IDs are appended to the report. Exact original quotations, pages and Unicode spans remain in the accepted downloadable paper_summary.json evidence file named by the manifest. No new experiment, benchmark or unseen source inspection is claimed.'),
                    _port('delivery_manifest', 'paper_delivery_manifest', MANIFEST,
                    'JSON manifest of exact accepted Brief, summary, canonical source texts, prior advancing gates and Markdown report. All files have safe relative paths and researcher audience; missing_evidence is empty. Source-file identity is protected host assurance, not a blind reviewer lookup.') ]}
            keys, questions = DELIVERY_CHECKS, delivery_questions
        else:
            keys = tuple(declaration['guarantees']['acceptance'])
            questions = []
        stage_runner = runner_ref
        if stage == 'paper_planner':
            planning_closure = {name: store.put_blob((root / name).read_bytes(), media_type='text/x-python')
                for name in ('planning.py', 'summary_planning.py', 'unified_planning.py', 'binding.py')}
            stage_runner = store.put_blob(json_bytes({'implementation': 'research.planning.planner_checks', 'files': planning_closure}), media_type='application/json')
            questions = [
                ('graph_self_consistent', 'Is the declared predecessor/future graph internally acyclic and resolved?'),
                ('output_ports_named', 'Does every future output name a compatible listed producer port?'),
                ('coverage_tags_present', 'Does every node have a requirement or deliverable tag?'),
                ('coverage_map_consistent', 'For requirement and deliverable entries, is coverage the exact inverse of the corresponding node tags? For evidence_obligation entries, do node_ids name existing nodes without requiring a matching node tag?'),
                ('no_authority_claims', 'Do notes, objectives and suggested checks avoid commands or authority claims?')]
        ports = [port['name'] for port in declaration['ports']['outputs']]
        checks = [{'check_id': key, 'target_port': ('delivery_manifest' if 'manifest' in key or 'links' in key else ports[0]),
            'rule_summary': 'Exact declared structure and protected original input/source/output custody: ' + key,
            'runner_ref': stage_runner, 'reads': ['output'] if key.endswith('_schema') else ['output', 'inputs', 'runtime_records'],
            'blocking': True} for key in keys]
        for port in declaration['ports']['outputs']:
            port['check_ids'] = [row['check_id'] for row in checks if row['target_port'] == port['name']]
        declaration['guarantees']['checks'] = [{'id': row['check_id'], 'kind': 'deterministic',
            'target': 'outputs.' + row['target_port'], 'runner': {'ref': 'protected_paper_checks', 'sha256': stage_runner['sha256']},
            'anchor': 'exact original sources and output bytes', 'over': ['outputs'], 'author': 'independent check owner',
            'written_before_body': True, 'held_out': False, 'signal_source': 'captured output and original run records',
            'owner': 'protected profile registry', 'assurance': 'deterministic host check'} for row in checks]
        declaration['guarantees']['acceptance'] = list(keys)
        bundle = {'schema_version': '1.0.0', 'id': NAMES[stage] + '.checks:' + release,
            'bundle_id': NAMES[stage] + '.checks', 'version': '1.0.0', 'target_cc_name': NAMES[stage],
            'target_cc_version_range': release, 'checks': checks, 'owner_role': 'verifier_owner'}
        criteria = [{'criterion_id': key, 'question': question, 'blocking': True,
            'answerable_from': 'declaration_and_output', 'target_port': None} for key, question in [*generic, *questions]]
        review = base_review
        if stage == 'paper_planner':
            review += b'\nCoverage entries of item_kind requirement/deliverable invert matching node tags. Evidence obligations only name existing nodes; no evidence-obligation node tag exists, so do not require inverse matching for these entries. Hidden Brief fidelity belongs to protected host checks, not this output-only review.\n'
        instruction_ref = store.put_blob(frozen_output_instructions(review, declaration), media_type='text/plain')
        profile = {'schema_version': '1.0.0', 'id': NAMES[stage] + '.profile:' + release,
            'profile_id': NAMES[stage] + '.profile', 'version': '1.0.0', 'target_cc_name': NAMES[stage],
            'target_cc_version_range': release, 'criteria': criteria, 'instruction_ref': instruction_ref,
            'model_call_limit': 1, 'time_s': 90, 'owner_role': 'verifier_owner'}
        result[stage] = {'declaration_ref': store.put_record('capsule-declaration', declaration),
            'body_refs': body_refs, 'bundle_ref': store.put_record('check-bundle', bundle),
            'profile_ref': store.put_record('checking-profile', profile), 'runner_ref': stage_runner,
            'implementation_refs': tuple(ref for name, ref in body_refs.items() if name != 'capsules/_common.py')}
    if verify_catalog:
        frozen = json.loads((root / 'resources/capsules/paper_catalog.json').read_text('utf-8'))
        if frozen != json.loads(json_bytes(result)):
            raise ResearchError('paper_catalog_pin_mismatch', 'Installed paper release differs from fixed declaration/body/check/profile catalog')
    return result


def register_paper_capsules(registry, check_registry, library, store, *, assets=None):
    from . import paper_summary, paper_delivery, paper_planner
    from ..checks.paper import PaperChecks
    from ..planning import planner_checks
    assets = assets or build_paper_assets(store)
    for stage, asset in assets.items():
        declaration = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
        identity = declaration['identity']
        entry = library.get(identity['name'], identity['version_label'])
        association = library.association(asset['declaration_ref'])
        if (entry['standing'] != 'active' or entry['declaration_ref'] != asset['declaration_ref']
                or entry['body_refs'] != asset['body_refs'] or association['bundle_ref'] != asset['bundle_ref']
                or association['profile_ref'] != asset['profile_ref']):
            raise ResearchError('paper_carrier_unadmitted', 'Paper carrier/check/profile is not its exact active admitted release')
        bundle = store.read_record(asset['bundle_ref'], contract_id='check-bundle')
        check_registry.register_bundle(bundle['bundle_id'], [row['check_id'] for row in bundle['checks']],
            planner_checks if stage == 'paper_planner' else PaperChecks(stage),
            implementation_ref=asset['runner_ref'], profile_ref=asset['profile_ref'])
        handler = {'paper_summary': paper_summary.execute, 'paper_delivery': paper_delivery.execute,
                   'paper_planner': paper_planner.execute}[stage]
        registry.register(identity['name'], identity['version_label'], handler,
            declaration_sha256=asset['declaration_ref']['sha256'], implementation_refs=asset['implementation_refs'])
    return assets
