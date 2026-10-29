"""Mandatory deterministic research checks; workers cannot weaken these checks."""
from __future__ import annotations

import ast
import hashlib
import io
import re
import stat
import zipfile
from collections.abc import Mapping, Sequence

from jiuwenswarm.research.environment import parse_requirements
from jiuwenswarm.research.science import ScienceError, classify_metric, close, finite, overall_classification, validate_rule_regions, validate_empirical, metric_payload


class CheckError(ValueError):
    def __init__(self, check_id: str, detail: str = ''):
        self.check_id = check_id
        super().__init__(check_id + (': ' + detail if detail else ''))


FORBIDDEN_MODULES = frozenset({'os', 'sys', 'subprocess', 'requests', 'urllib', 'shutil'})
BUNDLE_FILES = frozenset({'requirements.txt', 'poc_patch.py', 'run_benchmark.py'})
REPORT_HEADINGS = ('1. Objective', '2. Opportunity and citations', '3. Hypothesis and registered criteria',
                   '4. Method and POC', '5. Results: baseline vs treatment', '6. Scientific verdict and reasoning',
                   '7. Limitations and risks', '8. Follow-up recommendations', '9. Reproducibility')


def report_sections(report: bytes | str) -> list[str]:
    if isinstance(report, bytes):
        report = report.decode('utf-8', errors='strict')
    if not report.startswith('# '):
        raise CheckError('research_report_schema')
    matches = list(re.finditer(r'^## (.+)$', report, re.MULTILINE))
    if [m[1].strip() for m in matches] != list(REPORT_HEADINGS):
        raise CheckError('required_sections')
    sections = [report[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(report)].strip() for i, m in enumerate(matches)]
    if any(not text for text in sections):
        raise CheckError('required_sections')
    for i, section in enumerate(sections):
        if i != 7 and 'Recommendation:' in section:
            raise CheckError('recommendation_labeling')
        if i == 7 and any(re.match(r'^\s*[-*+]\s+', line) and not re.match(r'^\s*[-*+]\s+Recommendation:', line) for line in section.splitlines()):
            raise CheckError('recommendation_labeling')
    return sections


def _python_check(name: str, content: bytes) -> tuple[ast.AST, dict]:
    try:
        tree = ast.parse(content, filename=name)
        compile(tree, name, 'exec')  # compile only; never evaluate/import generated code
    except (SyntaxError, ValueError, TypeError) as exc:
        raise CheckError('python_syntax', str(exc)[:500]) from exc
    forbidden = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            forbidden.update(n.name.split('.')[0] for n in node.names if n.name.split('.')[0] in FORBIDDEN_MODULES | {'importlib'})
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module.split('.')[0]
            if module in FORBIDDEN_MODULES | {'importlib'}:
                forbidden.add(module)
        elif isinstance(node, ast.Name) and node.id in {'__import__', 'exec', 'eval', 'importlib'}:
            forbidden.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in {'__import__', 'exec', 'eval', 'import_module'}:
            forbidden.add(node.attr)
    if forbidden:
        raise CheckError('forbidden_imports', ','.join(sorted(forbidden)))
    return tree, {'path': name, 'sha256': hashlib.sha256(content).hexdigest(),
                  'syntax_result': 'pass', 'syntax_detail': None, 'forbidden_imports': []}


def inspect_bundle(content: bytes, metric_ids: Sequence[str], lock_pins: Mapping[str, str]) -> dict:
    if len(content) > 1024 * 1024:
        raise CheckError('archive_size')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) != 3 or {x.filename for x in entries} != BUNDLE_FILES:
                raise CheckError('archive_members')
            if any(x.flag_bits & 1 or stat.S_ISLNK(x.external_attr >> 16) or x.is_dir() for x in entries):
                raise CheckError('archive_members', 'encrypted/link/directory entry')
            if sum(x.file_size for x in entries) > 1024 * 1024:
                raise CheckError('archive_size', 'expanded content exceeds bound')
            files = {x.filename: archive.read(x) for x in entries}
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise CheckError('archive_valid') from exc
    dependencies = parse_requirements(files['requirements.txt'])
    if len(dependencies) > 50 or any(lock_pins.get(k) != v for k, v in dependencies.items()):
        raise CheckError('dependencies_match_lock')
    checks = [{'path': 'requirements.txt', 'sha256': hashlib.sha256(files['requirements.txt']).hexdigest(),
               'syntax_result': 'not_applicable', 'syntax_detail': None, 'forbidden_imports': []}]
    for name in ['poc_patch.py', 'run_benchmark.py']:
        tree, checked = _python_check(name, files[name]); checks.append(checked)
        if name != 'run_benchmark.py':
            continue
        prints = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'print']
        matching = [n for n in prints if len(n.args) == 1 and not n.keywords
                    and isinstance(n.args[0], ast.Call) and isinstance(n.args[0].func, ast.Attribute)
                    and isinstance(n.args[0].func.value, ast.Name) and n.args[0].func.value.id == 'json'
                    and n.args[0].func.attr == 'dumps' and len(n.args[0].args) == 1]
        metrics_found = any(isinstance(n.args[0].args[0], ast.Dict)
                            and any(isinstance(k, ast.Constant) and k.value == 'metrics' for k in n.args[0].args[0].keys)
                            for n in matching)
        constants = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        missing = sorted(set(metric_ids) - constants)
        output = {'result': 'pass' if len(prints) == len(matching) == 1 and metrics_found and not missing else 'fail',
                  'json_print_calls': len(matching), 'metrics_key_found': metrics_found, 'missing_metric_ids': missing}
    if output['result'] != 'pass':
        raise CheckError('output_log_format')
    return {'file_checks': checks, 'output_format_check': output,
            'dependencies': [{'name': n, 'version': v} for n, v in dependencies.items()], 'files': files}


def validate_search(scope: Mapping, output: Mapping, read_blob) -> None:
    queries, citations, ideas = output['queries'], output['citations'], output['ideas']
    if (not 1 <= len(queries) <= scope['max_queries'] or len(set(queries)) != len(queries)
            or any(not isinstance(q, str) or not 3 <= len(q) <= 200 for q in queries)):
        raise CheckError('queries_within_bounds')
    if not citations:
        raise CheckError('no_evidence')
    if not 1 <= len(ideas) <= 3:
        raise CheckError('idea_count')
    if len({i['idea_id'] for i in ideas}) != len(ideas) or len({c['id'] for c in citations}) != len(citations):
        raise CheckError('idea_ids_unique')
    citation_ids = {c['id'] for c in citations}
    if any(not i['citation_ids'] or not set(i['citation_ids']) <= citation_ids for i in ideas):
        raise CheckError('idea_citations_resolve')
    outcomes = output['connector_outcomes']
    if len(outcomes) != len(scope['connectors']) or {r['connector'] for r in outcomes} != set(scope['connectors']):
        raise CheckError('connector_outcomes')
    used = set()
    for row in outcomes:
        count = sum(c['connector'] == row['connector'] for c in citations)
        if count != row['citations_captured'] or row['status'] not in {'used', 'unavailable'} or not row['reason']:
            raise CheckError('connector_outcomes')
        if row['status'] == 'unavailable' and count:
            raise CheckError('connector_outcomes')
        if row['status'] == 'used':
            used.add(row['connector'])
    hits = {}
    for citation in citations:
        if citation['query'] not in queries or citation['connector'] not in used:
            raise CheckError('citation_query_ran')
        ref = citation['source_ref']; raw = read_blob(ref)
        if hashlib.sha256(raw).hexdigest() != ref['sha256']:
            raise CheckError('citation_source_resolves')
        if citation['connector'] == 'local_documents' and ref not in scope['local_document_refs']:
            raise CheckError('citation_source_resolves')
        try:
            # Citation offsets count code points in UTF-8 with line endings unchanged.
            text = raw.decode('utf-8')
        except UnicodeError as exc:
            raise CheckError('citation_source_resolves') from exc
        start, end = citation['char_start'], citation['char_end']
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text) or text[start:end] != citation['excerpt'] or not 1 <= len(citation['excerpt']) <= 2000:
            raise CheckError('excerpt_matches_source')
        if hashlib.sha256(citation['excerpt'].encode('utf-8')).hexdigest() != citation['excerpt_sha256']:
            raise CheckError('excerpt_hash')
        if citation['connector'] != 'local_documents':
            key = (citation['connector'], citation['query'])
            hits.setdefault(key, set()).add((ref['id'], ref['sha256']))
    if any(len(refs) > scope['max_hits_per_query'] for refs in hits.values()):
        raise CheckError('hit_limit')


def rank_opportunities(ideas: Sequence[Mapping], scores: Sequence[Mapping], rubric: Mapping) -> tuple[list[dict], str]:
    ids = [x['id'] if 'id' in x else x['idea_id'] for x in ideas]
    if len(set(ids)) != len(ids) or {x['idea_id'] for x in scores} != set(ids) or len(scores) != len(ids):
        raise CheckError('scores_cover_candidates')
    dimensions = ['novelty', 'feasibility', 'compute_alignment']
    names=[x['name'] for x in rubric['dimensions']]
    if len(names)!=len(dimensions) or set(names)!=set(dimensions) or not 50 <= rubric['reason_max_chars'] <= 500:
        raise CheckError('rubric_valid')
    eligible = []
    for score in scores:
        idea = ideas[ids.index(score['idea_id'])]
        if any(type(score.get(d)) is not int or not 1 <= score[d] <= 5 for d in dimensions):
            raise CheckError('scores_in_range')
        if score.get('total') != sum(score[d] for d in dimensions):
            raise CheckError('totals_recomputed')
        for d in dimensions:
            reason = score.get(d + '_reason')
            if not isinstance(reason, str) or not 1 <= len(reason) <= rubric['reason_max_chars']:
                raise CheckError('reason_length')
        text = ' '.join([idea.get('title', ''), idea.get('summary', ''), *idea.get('assumptions', []), *idea.get('risks', [])]).lower()
        hits = {d['id'] for d in rubric['forbidden_dependencies'] if any(term.lower() in text for term in d['match_terms'])}
        flags = score.get('dependency_flags', [])
        allowed_flags = {d['id'] for d in rubric['forbidden_dependencies']}
        if not hits <= set(flags) or not set(flags) <= allowed_flags or score.get('eligible') is not (not flags):
            raise CheckError('dependency_filter')
        if not set(score['citation_ids']) <= set(idea['citation_ids']):
            raise CheckError('score_citations_in_idea')
        if score.get('disposition') == 'deferred' or (flags and score.get('disposition') != 'rejected'):
            raise CheckError('dispositions_valid')
        if not flags:
            eligible.append(score)
    eligible.sort(key=lambda s: (-s['total'], s['idea_id']))
    if not eligible:
        raise CheckError('no_eligible_idea')
    selected = eligible[0]['idea_id']
    for score in scores:
        expected = 'selected' if score['idea_id'] == selected else 'eligible' if score['eligible'] else 'rejected'
        if score.get('disposition') != expected or not score.get('disposition_reason'):
            raise CheckError('dispositions_valid')
    return [{'rank': i + 1, 'idea_id': s['idea_id'], 'total': s['total']} for i, s in enumerate(eligible)], selected


def validate_scientific_verdict(blueprint: Mapping, payload: Mapping, verdict: Mapping) -> None:
    metric_ids = [m['metric_id'] for m in blueprint['metrics']]
    if [x['metric_id'] for x in payload['metrics']] != metric_ids or [x['metric_id'] for x in verdict['findings']] != metric_ids:
        raise CheckError('findings_cover_metrics')
    rules = {r['metric_id']: r for r in blueprint['outcome_rules']}
    classifications, unmeasured = [], False
    for metric, finding in zip(payload['metrics'], verdict['findings']):
        baseline, treatment = metric['baseline']['value'], metric['treatment']['value']
        classification, applied, expected_threshold = classify_metric(baseline, treatment, rules[metric['metric_id']])
        if finding['baseline_value'] != baseline or finding['treatment_value'] != treatment:
            raise CheckError('values_copied')
        if finding['classification'] != classification or finding['rule_applied'] != applied:
            raise CheckError('findings_recomputed')
        if (expected_threshold is None and finding['threshold'] is not None) or (expected_threshold is not None and not close(finding['threshold'], expected_threshold)):
            raise CheckError('threshold_recomputed')
        classifications.append(classification); unmeasured |= applied == 'unmeasured'
    plausibility = verdict['plausibility']['status']
    if verdict['aggregation_rule'] != 'm1_conjunctive_v1' or verdict['classification'] != overall_classification(classifications, plausibility):
        raise CheckError('overall_verdict_recomputed')
    if verdict['completeness']['status'] != ('incomplete' if unmeasured else 'complete'):
        raise CheckError('completeness_matches_payload')
    if bool(verdict['blockers']) != (unmeasured or plausibility == 'implausible'):
        raise CheckError('blockers_consistent')
    if plausibility != 'plausible' and not verdict['plausibility']['notes']:
        raise CheckError('plausibility_notes')


def validate_blueprint(blueprint: Mapping, brief: Mapping, baseline: Mapping, validation: Mapping, read_blob) -> None:
    ids = [m['metric_id'] for m in blueprint['metrics']]
    rules = blueprint['outcome_rules']
    if len(set(ids)) != len(ids) or len(rules) != len(ids) or {r['metric_id'] for r in rules} != set(ids):
        raise CheckError('rules_reference_declared_metrics')
    if len(blueprint['dependent_variables']) != len(ids) or set(blueprint['dependent_variables']) != set(ids):
        raise CheckError('dependent_variables_match_metrics')
    if not baseline['environment_ref'] or baseline['environment_ref'] != validation['environment_ref'] or blueprint['environment_ref'] != baseline['environment_ref']:
        raise CheckError('environment_from_resources')
    if baseline['availability'] != 'available' or validation['availability'] != 'available':
        raise CheckError('resource_refs_resolve')
    identity = blueprint['baseline_identity']
    if identity['revision'] != baseline['revision'] or identity['entry_point'] not in {f['path'] for f in baseline['files']}:
        raise CheckError('baseline_identity_resolves')
    if set((r['id'], r['sha256']) for r in blueprint['resource_refs']) != {
            (identity['resource_ref']['id'], identity['resource_ref']['sha256']),
            (blueprint['validation_resource_ref']['id'], blueprint['validation_resource_ref']['sha256'])}:
        raise CheckError('resource_refs_resolve')
    for ref in [*blueprint['resource_refs'], blueprint['brief_ref'], blueprint['opportunity_ref'], blueprint['environment_ref']]:
        if hashlib.sha256(read_blob(ref)).hexdigest() != ref['sha256']:
            raise CheckError('resource_refs_resolve')
    if not {c['text'] for c in brief['constraints']} <= set(blueprint['constraints']):
        raise CheckError('constraints_carried')
    target_metrics = {m['target_id']: m for m in blueprint['metrics'] if m.get('target_id') is not None}
    for target in brief['target_metrics']:
        if target['id'] not in target_metrics:
            raise CheckError('brief_targets_covered')
        m = target_metrics[target['id']]
        if target.get('comparison'):
            comparison = target['comparison']
            from ..target_comparisons import comparison_rule
            try:expected = comparison_rule(target, m['unit'])
            except ValueError as exc:raise CheckError('brief_comparison_consistent', str(exc)) from exc
            if next(r for r in rules if r['metric_id'] == m['metric_id'])['success'] != expected:
                raise CheckError('brief_comparison_consistent')
    for metric in blueprint['metrics']:
        validate_rule_regions(next(r for r in rules if r['metric_id'] == metric['metric_id']), metric['direction'])
        if metric['valid_min'] is not None and metric['valid_max'] is not None and metric['valid_min'] > metric['valid_max']:
            raise CheckError('blueprint_schema')


def validate_benchmark(blueprint, manifest, payload, receipt, provisioning, empirical, read_blob, *, lock_pins):
    ids = [m['metric_id'] for m in blueprint['metrics']]
    count, runs = blueprint['repeat_count'], receipt['runs']
    validate_empirical(empirical['runs'], ids, [r['sequence'] for r in runs])
    if len(runs) != 2 * count or [r['role'] for r in runs] != ['baseline'] * count + ['treatment'] * count:
        raise CheckError('baseline_before_treatment')
    if [r['repeat_index'] for r in runs] != list(range(count)) * 2 or any(r['seed'] != blueprint['seed'] for r in runs):
        raise CheckError('protocol_matches_blueprint')
    if any(a['started_at'] > b['started_at'] for a, b in zip(runs, runs[1:])):
        raise CheckError('baseline_before_treatment')
    for run in runs:
        expected_subject = blueprint['baseline_identity']['resource_ref'] if run['role'] == 'baseline' else manifest['archive_ref']
        if run['subject_ref'] != expected_subject or run['timeout_s'] <= 0 or run['wall_time_s'] < 0:
            raise CheckError('baseline_unmodified')
        if run['role'] == 'baseline' and (run['exit_code'] != 0 or not any(arg.endswith(blueprint['baseline_identity']['entry_point']) for arg in run['command'])):
            raise CheckError('baseline_unmodified')
        if run['hardware_ref'] != receipt['hardware_inventory']['hardware_id']:
            raise CheckError('hardware_inventory_captured')
        read_blob(run['stdout_ref']); read_blob(run['stderr_ref'])
    if payload['run_order'] != [r['role'] for r in runs] or payload['repeat_count'] != count or payload['seed'] != blueprint['seed']:
        raise CheckError('protocol_matches_blueprint')
    if [m['metric_id'] for m in payload['metrics']] != ids:
        raise CheckError('metric_coverage')
    if payload['environment_lock_ref'] != blueprint['environment_ref'] or manifest['environment_ref'] != blueprint['environment_ref'] or provisioning['environment_lock_ref'] != blueprint['environment_ref']:
        raise CheckError('environment_lock_match')
    from ..environment import verify_provisioned_inventory
    verify_provisioned_inventory(lock_pins, provisioning['packages'])
    if provisioning['status'] != 'succeeded' or provisioning['unlisted_network_requests'] != 0:
        raise CheckError('network_policy_respected')
    if provisioning['network_policy_used'] not in {'none', 'allowlist'}:
        raise CheckError('network_policy_respected')
    raw_refs = {(r['id'], r['sha256']) for r in payload['raw_evidence_refs']}
    required_raw = [receipt['empirical_results_ref']] + [r[k] for r in runs for k in ['stdout_ref', 'stderr_ref']]
    if not {(r['id'], r['sha256']) for r in required_raw} <= raw_refs:
        raise CheckError('raw_repeats_present')
    for metric, actual in zip(blueprint['metrics'], payload['metrics']):
        values, reasons = {}, {}
        for role in ['baseline', 'treatment']:
            pairs = [(run, row) for run, row in zip(runs, empirical['runs']) if run['role'] == role]
            values[role] = [row['metrics'][metric['metric_id']] for run, row in pairs if metric['metric_id'] in row['metrics']]
            missing = [row['unmeasured_metrics'][metric['metric_id']] for run, row in pairs if metric['metric_id'] not in row['metrics']]
            reasons[role] = missing[0] if missing else None
        expected = metric_payload(metric, values['baseline'], values['treatment'], count, reasons['baseline'], reasons['treatment'])
        for key in ['metric_id', 'unit', 'aggregation']:
            if actual[key] != expected[key]:
                raise CheckError('protocol_matches_blueprint')
        for role in ['baseline', 'treatment']:
            if actual[role]['repeats'] != expected[role]['repeats']:
                raise CheckError('values_match_empirical_results')
            a, b = actual[role]['value'], expected[role]['value']
            if (b is None and a is not None) or (b is not None and not close(a, b)) or actual[role]['unmeasured_reason'] != expected[role]['unmeasured_reason']:
                raise CheckError('arithmetic_consistent')
        if (expected['delta'] is None and actual['delta'] is not None) or (expected['delta'] is not None and not close(actual['delta'], expected['delta'])):
            raise CheckError('arithmetic_consistent')


def _refs(value):
    if isinstance(value, dict):
        if set(value) == {'id', 'sha256'}:
            yield value
        else:
            for item in value.values():
                yield from _refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from _refs(item)


def _markdown_table(section, columns):
    rows = [[cell.strip().strip('`') for cell in line.strip().strip('|').split('|')]
            for line in section.splitlines() if line.strip().startswith('|')]
    for index, row in enumerate(rows):
        if row == columns:
            body = rows[index + 2:]
            if not body or any(len(item) != len(columns) for item in body):
                break
            return body
    raise CheckError('report_table', 'Required table or exact columns are absent')


def validate_delivery(inputs, input_refs, manifest, report_bytes, read_blob):
    """Cross-check the report/manifest against exact accepted lifecycle inputs."""
    from ..contracts import validate
    from ..inspection import safe_named_path
    import json
    validate('delivery-manifest', manifest)
    try:
        report = report_bytes.decode('utf-8', errors='strict')
    except UnicodeError as exc:
        raise CheckError('research_report_schema') from exc
    sections = report_sections(report)
    # report_sections returns bodies in source section order.
    if isinstance(sections, dict):
        sections = list(sections.values())
    for ref in _refs(manifest):
        if hashlib.sha256(read_blob(ref)).hexdigest() != ref['sha256']:
            raise CheckError('ref_hash_match')
    files = manifest['files']; roles = {}
    for file in files:
        if not safe_named_path(file['path']) or file['path'] != file['path'].lower():
            raise CheckError('delivery_manifest_schema')
        roles.setdefault(file['role'], []).append(file)
    singles = {'report': None, 'brief': 'brief', 'candidate_set': 'candidate_set', 'screening': 'screening_result',
               'opportunity': 'opportunity_card', 'hypothesis': 'hypothesis_blueprint', 'poc_manifest': 'poc_manifest',
               'poc_bundle': None, 'benchmark': 'benchmark_payload', 'verdict': 'evaluation_verdict'}
    if any(len(roles.get(role, [])) != 1 for role in singles):
        raise CheckError('manifest_completeness')
    if manifest['brief_ref'] != input_refs['brief'] or manifest['verdict_ref'] != input_refs['evaluation_verdict']:
        raise CheckError('manifest_completeness')
    if manifest['report_ref'] != roles['report'][0]['artifact_ref'] or hashlib.sha256(report_bytes).hexdigest() != manifest['report_ref']['sha256']:
        raise CheckError('ref_hash_match')
    for role, port in singles.items():
        if port and roles[role][0]['artifact_ref'] != input_refs[port]:
            raise CheckError('manifest_completeness')
    bundle_ref = inputs['poc_manifest']['archive_ref']
    if roles['poc_bundle'][0]['artifact_ref'] != bundle_ref:
        raise CheckError('manifest_completeness')
    expected_artifacts = [input_refs[port] for port in ['candidate_set', 'screening_result', 'opportunity_card',
                          'hypothesis_blueprint', 'poc_manifest', 'benchmark_payload', 'evaluation_verdict']]
    if any(ref not in manifest['artifact_refs'] for ref in expected_artifacts) or len({r['id'] for r in manifest['artifact_refs']}) != len(manifest['artifact_refs']):
        raise CheckError('manifest_completeness')
    expected_gates = [entry['gate_decision_ref'] for entry in inputs['gate_decision_index']['entries']]
    if manifest['gate_decision_refs'] != expected_gates or any(ref not in [f['artifact_ref'] for f in roles.get('gate_decision', [])] for ref in expected_gates):
        raise CheckError('manifest_completeness')
    for ref in expected_gates:
        if json.loads(read_blob(ref))['action'] != 'advance':
            raise CheckError('manifest_completeness')
    required_raw = [r[key] for r in inputs['execution_receipt']['runs'] for key in ['stdout_ref', 'stderr_ref']]
    if len(roles.get('raw_evidence', [])) < 2 or any(ref not in [f['artifact_ref'] for f in roles['raw_evidence']] for ref in required_raw):
        raise CheckError('manifest_completeness')
    if len(roles.get('environment', [])) < 2 or any(input_refs[port] not in [f['artifact_ref'] for f in roles['environment']] for port in ['environment_lock', 'run_configuration']):
        raise CheckError('manifest_completeness')
    allowed = [*input_refs.values(), *expected_gates, bundle_ref, manifest['report_ref'],
               *inputs['benchmark_payload']['raw_evidence_refs'], *required_raw,
               *[f['artifact_ref'] for f in inputs['poc_manifest']['files']]]
    if any(ref not in allowed for ref in [*manifest['artifact_refs'], *[f['artifact_ref'] for f in files]]):
        raise CheckError('manifest_completeness', 'Manifest introduced an unbound artifact')
    if any(item['blocking'] for item in manifest['missing_evidence']):
        raise CheckError('negative_result_delivered', 'Blocking missing evidence prevents release')
    payload, blueprint, verdict = inputs['benchmark_payload'], inputs['hypothesis_blueprint'], inputs['evaluation_verdict']
    results = _markdown_table(sections[4], ['Metric', 'Unit', 'Baseline', 'Treatment', 'Delta'])
    if len(results) != len(payload['metrics']) or {r[0] for r in results} != {m['metric_id'] for m in payload['metrics']}:
        raise CheckError('results_table_matches_payload')
    for row in results:
        metric = next(m for m in payload['metrics'] if m['metric_id'] == row[0])
        if row[1] != metric['unit']:
            raise CheckError('results_table_matches_payload')
        for text, value in zip(row[2:], [metric['baseline']['value'], metric['treatment']['value'], metric['delta']]):
            if value is None:
                if text.lower() not in {'null', 'unavailable'}:
                    raise CheckError('results_table_matches_payload')
            else:
                try:
                    parsed = float(text)
                    if not finite(parsed) or parsed != value:
                        raise ValueError()
                except (ValueError, ScienceError) as exc:
                    raise CheckError('results_table_matches_payload') from exc
    criteria = _markdown_table(sections[2], ['Metric', 'Unit', 'Aggregation', 'Success rule', 'Falsification rule', 'Otherwise'])
    if len(criteria) != len(blueprint['metrics']) or {r[0] for r in criteria} != {m['metric_id'] for m in blueprint['metrics']}:
        raise CheckError('criteria_match_blueprint')
    for row in criteria:
        metric = next(m for m in blueprint['metrics'] if m['metric_id'] == row[0])
        if row[1:3] != [metric['unit'], metric['aggregation']]:
            raise CheckError('criteria_match_blueprint')
    lines = [line.strip() for line in sections[5].splitlines() if line.strip()]
    expected = ['Classification: ' + verdict['classification'], 'Completeness: ' + verdict['completeness']['status'],
                'Plausibility: ' + verdict['plausibility']['status']]
    expected += [f"- {f['metric_id']}: {f['classification']}. {f['rationale']}" for f in verdict['findings']]
    if lines[:3] != expected[:3] or [line for line in lines[3:] if line.startswith('- ')] != expected[3:]:
        raise CheckError('verdict_matches_evaluation')
    carried = [*verdict['blockers'], *verdict['residual_risks'], *verdict['completeness']['notes'], *verdict['plausibility']['notes']]
    if any('- ' + text not in sections[6] for text in carried):
        raise CheckError('carried_content')
    if any('Risk from the opportunity card: ' + risk not in sections[6] for risk in inputs['opportunity_card']['risks']):
        raise CheckError('carried_content')
    if any('Recommendation: ' + text not in sections[7] for text in verdict['followups']) or any(cid not in sections[1] for cid in inputs['opportunity_card']['citation_ids']):
        raise CheckError('carried_content')
    pins = _markdown_table(sections[8], ['Item', 'Id', 'sha256'])
    expected_pins = {'Research brief': input_refs['brief'], 'Hypothesis blueprint': input_refs['hypothesis_blueprint'],
                     'POC manifest': input_refs['poc_manifest'], 'POC bundle': bundle_ref,
                     'Environment lock': input_refs['environment_lock'], 'Run configuration': input_refs['run_configuration'],
                     'Benchmark payload': input_refs['benchmark_payload'], 'Evaluation verdict': input_refs['evaluation_verdict']}
    for label, ref in expected_pins.items():
        if [label, ref['id'], ref['sha256']] not in pins:
            raise CheckError('reproducibility_pins')
