"""Read-only experiment diagnosis and follow-up proposals for factory CCs.

These helpers expose uncertainties and bounded experiment designs. They never
choose/execute a host action, amend a contract, create a task, or grant effects.
Reports are evidence of what was recorded, not independently verified truth.
"""
from __future__ import annotations

import hashlib
import json
import math
from statistics import median

VERSION = '1.0.0'
ONTOLOGY = {
    'decode': {'question': 'What is on the decode critical path?', 'signals': ['decode_ms', 'generated_tokens', 'critical_path_wait_ms']},
    'prefill': {'question': 'Does prompt processing dominate request latency?', 'signals': ['prompt_ms', 'prompt_tokens', 'ttft_ms']},
    'placement': {'question': 'Does residency reduce demand stalls within host headroom?', 'signals': ['resident_expert_bytes', 'vram_hit', 'host_available_bytes']},
    'io': {'question': 'Are demand reads on the critical path?', 'signals': ['physical_read_bytes', 'demand_wait_ms', 'ready_at_demand_bytes']},
    'cpu': {'question': 'Are CPU scheduling or oversubscription delaying the GPU?', 'signals': ['cpu_time_ms', 'run_queue_wait_ms', 'cpu_quota']},
    'cache': {'question': 'How do initialization and fixed repeat workloads differ?', 'signals': ['physical_read_bytes', 'canonical_ids_sha256', 'cache_policy']},
    'draft': {'question': 'Does verified drafting save target work at fixed correctness?', 'signals': ['draft_accepted', 'draft_offered', 'decode_ms']},
    'quality': {'question': 'Are output and full-model obligations preserved?', 'signals': ['canonical_ids_sha256', 'finish_reason', 'effective_experts', 'task_accuracy']},
    'telemetry': {'question': 'Are results complete and observer costs bounded?', 'signals': ['collector_exit', 'container_removed', 'observer_overhead', 'artifact_integrity']},
}


def number(value, positive=False):
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


def _rows(document, depth=0, scope=None):
    """Normalize known retained envelopes without inventing comparison identity.

    Keep report-level verdicts alongside cells. A one-token prefill probe's
    decode interval is not a decode-throughput workload. Unknown envelopes stay
    visible as rows with absent metrics rather than acquiring fabricated data.
    """
    if not isinstance(document, dict):
        raise ValueError('Report must be a JSON object')
    if depth > 4:
        raise ValueError('Report envelope nesting exceeds the analysis bound')
    scope = document.get('scope', scope)
    if not isinstance(scope, str):
        scope = None
    for key in ('report', 'analysis'):
        if isinstance(document.get(key), dict):
            header = {k: v for k, v in document.items() if k != key}
            return ([dict(header, _metric_scope=scope)] if header else []) + _rows(document[key], depth + 1, scope)
    for key in ('measurements', 'results', 'cells'):
        if isinstance(document.get(key), list):
            rows = []
            if key == 'cells' or document.get('verdict'):
                rows.append(dict(document, _metric_scope=scope))
            for row in document[key]:
                if not isinstance(row, dict):
                    raise ValueError('Report episodes must be objects')
                rows.extend(_rows(row, depth + 1, scope))
            return rows
    return [dict(document, _metric_scope=scope)]


def _requests(row):
    requests = row.get('requests', [])
    return [r for r in requests if isinstance(r, dict)] if isinstance(requests, list) else []


def _identity(request):
    digest = request.get('canonical_sha256', request.get('canonical_ids_sha256'))
    if isinstance(digest, str) and len(digest) == 64:
        return digest
    ids = request.get('ids')
    if isinstance(ids, list) and ids and all(type(i) is int and i >= 0 for i in ids):
        return hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest()
    return None


def _repeatability(rows):
    groups = {}
    across = {}
    for row in rows:
        # A cell's configuration identifies its treatment. Never compare outputs
        # across differently configured cells to assert A/A correctness.
        per_cell = {}
        for request in _requests(row):
            identity = _identity(request)
            prompt = request.get('prompt')
            if not isinstance(prompt, str) and isinstance(request.get('prompt_sha256'), str):
                prompt = 'tokenized:' + request['prompt_sha256']
            if identity and isinstance(prompt, str):
                output = (identity, request.get('finish_reason', request.get('finish')))
                per_cell.setdefault(prompt, []).append(output)
                comparison = row.get('comparison_group')
                if isinstance(comparison, str) and len(comparison) == 64:
                    across.setdefault((comparison, prompt), {}).setdefault(id(row), []).append(output)
        for prompt, outputs in per_cell.items():
            if len(outputs) > 1:
                groups[(id(row), prompt)] = outputs
    for key, cells in across.items():
        if len(cells) > 1:
            groups[('cross-cell', *key)] = [output for outputs in cells.values() for output in outputs]
    if not groups:
        return {'status': 'not_established', 'matched_prompt_groups': 0}
    different = sum(len(set(group)) > 1 for group in groups.values())
    return {'status': 'different' if different else 'observed_equal',
            'matched_prompt_groups': len(groups), 'different_groups': different,
            'comparable_cross_cell_groups': sum(len(cells) > 1 for cells in across.values()),
            'limitation': 'Matching prompt repeats; cross-cell comparison only with an explicit identical experiment identity. Not an accuracy or performance-gain test.'}


def diagnose(reports, evidence_ids, objective='Improve inference performance'):
    """Summarize recorded facts and propose inspection priorities, not benefits."""
    if not isinstance(reports, list) or not reports or len(reports) > 20:
        raise ValueError('Supply 1..20 reports')
    episodes = []
    failures = []
    requests = []
    for source_index, report in enumerate(reports):
        for row in _rows(report):
            if not isinstance(row, dict):
                raise ValueError('Report episodes must be objects')
            episodes.append(row)
            status = row.get('status', row.get('execution_outcome', 'unknown'))
            if row.get('verdict') == 'scoped_correctness_failed' or row.get('correctness') == 'fail':
                failures.append({'source_index': source_index, 'status': 'correctness_failed',
                                 'verdict': row.get('verdict'), 'scope': row.get('_metric_scope')})
            elif status in {'failed', 'cancelled', 'oom_event', 'command_failed', 'measurement_failed', 'protocol_invalid'}:
                failures.append({'source_index': source_index, 'status': status,
                                 'error': row.get('error'), 'label': row.get('label', row.get('mode'))})
            requests.extend(dict(r, _metric_scope=row.get('_metric_scope')) for r in _requests(row))
    rates = []
    for request in requests:
        if request.get('_metric_scope') == 'prefill_microbenchmark':
            continue
        count, elapsed = request.get('generated_tokens'), request.get('decode_ms')
        if number(count, True) and number(elapsed, True):
            rates.append(count * 1000 / elapsed)
        else:
            value = request.get('native_decode_tps', request.get('decode_tps'))
            if number(value, True):
                rates.append(value)
    prefill_times = [r['prefill_ms'] for r in requests if number(r.get('prefill_ms'), True)]
    repeatability = _repeatability(episodes)
    orphan = any(row.get('container_still_running_after_collector_death') is True or
                 (row.get('container_removed') is False) for row in episodes)
    incomplete = any(row.get('final_report_missing_after_collector_death') is True for row in episodes)
    explicit_accuracy = [row.get('semantic_accuracy') for row in episodes if row.get('semantic_accuracy')]
    candidates = []

    def candidate(identifier, slice_id, hypothesis, prerequisites, change, why):
        candidates.append(dict(id=identifier, engine_slice=slice_id, hypothesis=hypothesis,
            prerequisites=prerequisites, single_change=change, evidence_ids=list(evidence_ids), reason=why,
            expected_benefit='unknown', status='proposal_only'))

    if orphan or incomplete:
        candidate('recover_before_scoring', 'telemetry', 'Independent recovery can preserve failed-run evidence and remove owned orphan workloads.',
                  ['exact durable ownership', 'fault-injection budget'], 'independent recorder recovery',
                  'Recorded collector death left an orphan or missing final report; throughput scoring must wait.')
    if failures:
        candidate('diagnose_failure', 'telemetry', 'The retained failure can be reproduced and classified without losing its evidence.',
                  ['bounded reproducer', 'host memory guard'], 'one failure reproducer',
                  'Failed attempts are retained and precede further optimization.')
    if repeatability['status'] != 'observed_equal':
        candidate('establish_repeatability', 'quality', 'A fixed no-draft/static-cache baseline can establish comparable output and latency.',
                  ['fixed model/tokenizer/workload', 'full-expert policy', 'explicit cache protocol'],
                  'diagnostic A/A campaign', 'Repeatability is different or not established; a treatment gain cannot yet be scored.')
    candidate('measure_io_readiness', 'io', 'Demand-readiness and critical-path waits can distinguish storage pressure from overlap.',
              ['phase boundaries', 'observer overhead bound'], 'readiness/wait instrumentation only',
              'A tokens/s number alone does not identify the limiting mechanism.')
    candidate('measure_cpu_scheduling', 'cpu', 'CPU queue and phase counters can show whether worker contention delays decode.',
              ['CPU quota recorded', 'no concurrent builds'], 'CPU scheduling observation only',
              'CPU scheduling is an alternative explanation to expert streaming.')
    candidate('measure_placement', 'placement', 'Residency and demand-stall measurements can justify one placement-budget trial.',
              ['host memory headroom', 'effective placement counters', 'repeatability'],
              'one resident-budget setting', 'More resident memory is not assumed to be faster.')
    if any(number(r.get('prefill_ms'), True) for r in requests):
        candidate('measure_prefill_chunk', 'prefill',
                  'A different native prefill chunk may reduce complete request latency on this hardware/model.',
                  ['positive native prefill timing', 'fixed decoding policy', 'full-six experts', 'combined prefill plus decode metric'],
                  'one prefill chunk setting',
                  'Recorded prefill cost warrants a bounded chunk comparison; a decode gain alone is insufficient.')
    offered = sum(r.get('draft_offered', r.get('offered_drafts', 0)) for r in requests if number(r.get('draft_offered', r.get('offered_drafts'))))
    accepted = sum(r.get('draft_accepted', r.get('accepted_drafts', 0)) for r in requests if number(r.get('draft_accepted', r.get('accepted_drafts'))))
    if offered:
        candidate('measure_draft_cost', 'draft', 'Draft cost and verified target work can explain whether actual draft engagement helps.',
                  ['same quality policy', 'effective draft state', 'A/A valid'],
                  'one draft setting', 'Accepted drafts establish engagement; acceptance ratio alone does not establish a speedup.')
    return dict(schema_version=1, methodology_version=VERSION, objective=objective,
                evidence_ids=list(evidence_ids), episodes=len(episodes), failures=failures,
                failure_count=len(failures), repeatability=repeatability,
                request_count=len(requests),
                prefill_ms=dict(count=len(prefill_times), minimum=min(prefill_times) if prefill_times else None,
                    median=median(prefill_times) if prefill_times else None, maximum=max(prefill_times) if prefill_times else None,
                    scope='descriptive across all retained requests including warmups; not a treatment effect'),
                decode_tps=dict(count=len(rates), minimum=min(rates) if rates else None,
                                median=median(rates) if rates else None, maximum=max(rates) if rates else None,
                                scope='descriptive across recorded requests; not a treatment effect'),
                draft_engagement=dict(accepted=accepted, offered=offered,
                                      acceptance_ratio=accepted/offered if offered else None),
                semantic_accuracy='not_established', recorded_accuracy_labels=explicit_accuracy,
                candidates=candidates, recommended_inspection=candidates[0]['id'],
                ontology=ONTOLOGY,
                constraints=['one hypothesis per trial', 'missing signal is unknown, not zero',
                             'diagnostic traces never score', 'failed/null episodes remain retained',
                             'no contract/grant mutation', 'no automatic task submission or CC promotion'])


def cache_protocol(analysis):
    return dict(schema_version=1, status='proposal_only', evidence_ids=analysis['evidence_ids'],
                phases=[{'name': 'first_after_initialization', 'fresh_container': True,
                         'description': 'First request after engine initialization; does not imply cold SSD.'},
                        {'name': 'repeat_fixed_workload', 'fresh_container': False,
                         'warmup_requests': 1, 'measured_requests': 1}],
                controls=['fixed model/pack/tokenizer/workload', 'disable prefix reuse',
                          'record effective placement/cache/draft state', 'record phase physical-read deltas',
                          'record host headroom and observer cost', 'no builds during measurement'],
                forbidden=['global cache eviction', 'calling hardlinks independent file cache',
                           'combining first/repeat as a causal A/B improvement'],
                maximum_completed_cells=6)


def ablation(analysis, hypothesis_id=None):
    identifier = hypothesis_id or analysis['recommended_inspection']
    matches = [candidate for candidate in analysis['candidates'] if candidate['id'] == identifier]
    if not matches:
        raise ValueError('hypothesis_id must identify a report-backed candidate')
    candidate = matches[0]
    scoring = (analysis['repeatability']['status'] == 'observed_equal'
               and not analysis['failures'] and identifier not in {
                   'recover_before_scoring', 'establish_repeatability', 'diagnose_failure',
                   'measure_io_readiness', 'measure_cpu_scheduling'})
    return dict(schema_version=1, status='proposal_only', candidate=candidate,
                mode='single_variable_abba_after_admission' if scoring else 'diagnostic_non_scoring',
                scoring_ready=False,  # within-cell equality is not a frozen A/A contract
                admission_requirements=['operator-frozen contract', 'independent A/A validity',
                                        'complete mechanism engagement', 'observer overhead within contract',
                                        'host admission and quiet lease'],
                maximum_changed_variables=1, maximum_trials=3,
                execution_order=['A', 'B', 'B', 'A'] if scoring else ['A', 'A', 'A'],
                freeze=['image/source identities except the declared change', 'workload/tokenizer/model',
                        'full-expert and correctness policy', 'cache/warmup protocol', 'resource limits'],
                stop_conditions=['correctness failure', 'memory guard/OOM', 'missing engagement',
                                 'incomplete evidence', 'budget exhausted'],
                final_combined_validation='Compare the final stack directly against the frozen original; do not multiply individual gains.')


def followup(analysis, task, hypothesis_id=None):
    design = ablation(analysis, hypothesis_id)
    candidate = design['candidate']
    return dict(schema_version=1, status='proposal_only', requires_operator_admission=True,
                source_task_id=task['task_id'], source_contract_id=task.get('contract_id'),
                evidence_ids=analysis['evidence_ids'], objective=candidate['hypothesis'],
                proposed_input=dict(objective=candidate['hypothesis'],
                    target=task.get('target'), engine_slice=candidate['engine_slice'],
                    hypothesis_id=candidate['id'], uncertainty=candidate['reason'],
                    expected_evidence=candidate['prerequisites'], experiment=design,
                    budget=dict(max_turns=24, wall_clock_s=14400, max_build_attempts=2, max_completed_gpu_cells=6)),
                contract_change='New contract revision requires operator freeze; this output does not amend or freeze any contract.',
                authority='Inherit no grants automatically. Operator task admission defines effects and source scope.',
                discovered_cc_candidate=dict(kind='method_or_component_candidate', engine_slice=candidate['engine_slice'],
                    hypothesis=candidate['hypothesis'], evidence_ids=analysis['evidence_ids'],
                    implementation_status='not_implemented', performance_benefit='unknown',
                    promotion='separate validation and operator authority required'))


def proposal_ablation(proposal, evidence_source):
    """Translate an immutable unmeasured hypothesis into an ablation design.

    This is design only. FactoryLoop.select remains the execution admission
    point for exact frozen templates and their allowed_hypothesis_ids.
    """
    from .hypotheses import validate
    from .store import encoded
    if not isinstance(proposal, dict):
        raise ValueError('Stored hypothesis proposal must be an object')
    identifier = proposal.get('hypothesis_id')
    hypothesis = validate(identifier, proposal.get('hypothesis'))
    digest = hashlib.sha256(encoded(hypothesis).encode('utf-8')).hexdigest()
    if (proposal.get('hypothesis_sha256') != digest
            or proposal.get('status') != 'proposed_unmeasured'
            or proposal.get('maximum_changed_variables') != 1
            or proposal.get('citations_unverified') is not True
            or proposal.get('citations_fetched') is not False
            or proposal.get('execution_authorized') is not False
            or proposal.get('promotion_authorized') is not False
            or proposal.get('correctness_status') != 'not_evaluated'
            or proposal.get('performance_status') != 'not_evaluated'):
        raise ValueError('Stored hypothesis payload/digest or unmeasured status differs')
    sources = proposal.get('evidence_sources')
    if (not isinstance(sources, list) or len(sources) != len(hypothesis['evidence_ids'])
            or any(not isinstance(row, dict) for row in sources)):
        raise ValueError('Stored hypothesis evidence provenance differs')
    if ([row.get('evidence_id') for row in sources] != hypothesis['evidence_ids']
            or any(not isinstance(row.get('task_id'), str) or not row['task_id']
                   or not isinstance(row.get('record_sha256'), str) or len(row['record_sha256']) != 64
                   or set(row['record_sha256']) - set('0123456789abcdef') for row in sources)):
        raise ValueError('Stored hypothesis evidence provenance differs')
    return dict(schema_version=1, status='proposal_only', hypothesis_id=identifier,
        hypothesis_sha256=digest, candidate=dict(id=identifier,
            hypothesis=hypothesis['mechanism'], applicability=hypothesis['applicability'],
            reason='Unmeasured agent hypothesis; transfer and causality remain uncertain. Falsification: ' + hypothesis['falsification'],
            single_change=hypothesis['changed_variable'], prediction=hypothesis['prediction'],
            required_counters=hypothesis['required_counters'], falsification=hypothesis['falsification'],
            correctness_obligations=hypothesis['correctness_obligations'],
            evidence_ids=hypothesis['evidence_ids'], evidence_sources=sources,
            primary_source_urls=hypothesis['primary_source_urls'],
            expected_benefit='unknown', status='proposal_only'),
        proposal_evidence_source=evidence_source, citations_unverified=True, citations_fetched=False,
        mode='single_variable_abba_after_admission', scoring_ready=False,
        maximum_changed_variables=1, maximum_trials=3, execution_order=['A', 'B', 'B', 'A'],
        required_counters=hypothesis['required_counters'], falsification=hypothesis['falsification'],
        correctness_obligations=hypothesis['correctness_obligations'],
        admission_requirements=['operator-frozen contract', 'independent A/A validity',
            'complete mechanism engagement', 'observer overhead within contract', 'host admission and quiet lease'],
        freeze=['image/source identities except the declared change', 'workload/tokenizer/model',
            'full-expert and correctness policy', 'cache/warmup protocol', 'resource limits'],
        stop_conditions=['correctness failure', 'memory guard/OOM', 'missing engagement',
            'incomplete evidence', 'budget exhausted'],
        execution_authorized=False, promotion_authorized=False,
        authority='Design only. Existing frozen-template selection remains the sole execution admission.',
        final_combined_validation='Compare the final stack directly against the frozen original; do not multiply individual gains.')


def dispatch(store, task_id, operation, inputs):
    allowed = {'evidence_ids', 'hypothesis_id'}
    if not isinstance(inputs, dict) or set(inputs) - allowed:
        raise ValueError('Methodology inputs allow evidence_ids and optional hypothesis_id')
    refs = inputs.get('evidence_ids')
    if not isinstance(refs, list) or not 1 <= len(refs) <= 20 or not all(isinstance(r, str) and r for r in refs):
        raise ValueError('evidence_ids must contain 1..20 task-scoped report IDs')
    task = store.get_task(task_id)
    reports = []
    sources = []
    proposals = []
    from .store import NotFound
    for ref in refs:
        for source_task in [task_id, *sorted(set(getattr(store, 'readable', ())) - {task_id})]:
            try:
                record = store.read(source_task, ref)
                break
            except NotFound:
                continue
        else:
            raise NotFound('Report evidence not found in authorized tasks')
        source = dict(task_id=source_task, evidence_id=ref)
        sources.append(source)
        if record.get('kind') == 'hypothesis_proposal':
            proposals.append((record.get('values'), source))
            continue
        if 'artifact_id' in record:
            if record['size'] > 4 * 1024 * 1024:
                raise ValueError('Report artifact exceeds 4 MiB analysis bound')
            report = json.loads(store.artifact_bytes(source_task, ref))
        elif 'values' in record:
            report = record['values']
        else:
            raise ValueError('Evidence must be a JSON report artifact or observation')
        reports.append(report)
    if operation == 'ablation' and proposals:
        matches = [(proposal, source) for proposal, source in proposals
                   if isinstance(proposal, dict) and proposal.get('hypothesis_id') == inputs.get('hypothesis_id')]
        if len(matches) > 1:
            raise ValueError('Ambiguous hypothesis proposal references')
        if matches:
            result = proposal_ablation(*matches[0])
            result['evidence_sources'] = sources
            return {'analysis': result}
    if not reports:
        raise ValueError('Supply measured report evidence or select an explicit proposed hypothesis for ablation')
    analysis = diagnose(reports, refs, task['objective'])
    analysis['evidence_sources'] = sources
    if operation == 'diagnose':
        result = analysis
    elif operation == 'cache_protocol':
        result = cache_protocol(analysis)
    elif operation == 'ablation':
        result = ablation(analysis, inputs.get('hypothesis_id'))
    elif operation == 'followup':
        result = followup(analysis, task, inputs.get('hypothesis_id'))
    else:
        raise ValueError('Unknown methodology capability')
    result['evidence_sources'] = sources
    return {'analysis': result}
