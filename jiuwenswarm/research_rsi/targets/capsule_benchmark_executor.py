"""Interface E: Root-side paired benchmark inside the loop grant/evaluator.

Served by both dispatchers (``WholeCapsuleDispatcher`` through the V18 kernel,
``LocalDispatcher`` in plain subprocesses) via their shared ``_run_job``
primitive, so every benchmark job gets the same claims, start records,
captures, sealing and budget accounting as an evaluation job. Ported from
Codex's ``capsule_benchmark_executor.py`` / ``capsule_semantic_executor.py``;
its separate benchmark/supplementary grants are replaced by the loop grant's
``max_executions`` (see ``capsule_executor.loop_execution_budget``).

Order of work for one call: semantic-edge cases (parent then candidate, each
once), then every benchmark case of every split -- timed cases
``repetitions`` x paired AB/BA, untimed cases once -- stopping at the first
correctness failure. Candidate correctness is judged against the paired
parent observation (``capsule_benchmark.judge``). Statistics are computed only
for a complete, correct run.
"""
from __future__ import annotations

import hashlib
import math
import statistics

from ..records import encoded
from .capsule_benchmark import (CORRECTNESS_CONTRACT, REPORT_SCHEMA, benchmark_config, benchmark_protocol,
    checker_passes, compare_paired_samples, effective_protocol, execution_plan, judge, need, observation,
    timing_batches, withheld_splits)
from .capsule_benchmark_runtime import BOOTSTRAP_SCHEMA, benchmark_job_assets, decode_benchmark_output
from .capsule_executor import failure_summary

EVIDENCE_SCHEMA = 'ai4r-rsi-capsule-benchmark-evidence:1'
SEMANTIC_REPORT_SCHEMA = 'ai4r-rsi-capsule-semantic-edges-report:1'
NODE_ID = 'unqualified-whole-capsule-benchmark'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _authorize(ledger, candidate_body, iteration):
    need(ledger.loop, 'BENCHMARK_REQUIRES_ITERATIVE_GRANT')
    need(not ledger.halted, 'DISPATCHER_HALTED_AFTER_UNKNOWN_EXECUTION')
    need(type(iteration) is int and 0 <= iteration <= 100000, 'FINITE_BENCHMARK_ITERATION_REQUIRED')
    need(isinstance(candidate_body, bytes) and 0 < len(candidate_body) <= 256 * 1024, 'EXACT_BOUNDED_CANDIDATE_BYTES_REQUIRED')
    if candidate_body == ledger.parent:
        # A/A baseline (parent against itself): calibrates the benchmark's own
        # noise; no candidate authority is involved.
        need('parent' in ledger.completed, 'BASELINE_MUST_COMPLETE_FIRST')
        ledger._live()
        return {'candidate_ref': ledger.parent_ref, 'binding_ref': None, 'iteration': 0}
    authorized = ledger.benchmarkable.get(digest(candidate_body))
    # Only a candidate this grant already evaluated under a Root binding.
    need(authorized is not None, 'BENCHMARK_CANDIDATE_MUST_BE_EVALUATED_FIRST')
    ledger._live()
    return authorized


class _Session:
    """One benchmark/semantic call: runs jobs and keeps the evidence trail."""

    def __init__(self, ledger, candidate_body, authorized, iteration, kind):
        self.ledger, self.body, self.authorized, self.iteration = ledger, candidate_body, authorized, iteration
        self.name = ledger.grant['capsule_name']
        self.sha = authorized['candidate_ref']['sha256']
        self.withheld = set(withheld_splits(self.name)) if kind == 'benchmark' else set()
        self.refs, self.cases, self.failure = [], [], None
        self.parent = {}           # (split, id) -> parent observation (reference)
        self.parent_checker = {}   # (split, id) -> parent passes checker
        self.started = ledger.executions

    def sealed(self, fixture):
        return fixture['split'] in self.withheld

    async def job(self, fixture, *, kind, repeat, role, batch, warmups):
        ledger = self.ledger
        body = ledger.parent if role == 'parent' else self.body
        ref = ledger.parent_ref if role == 'parent' else self.authorized['candidate_ref']
        binding_ref = self.authorized['binding_ref'] if role == 'candidate' else None
        # ``capsule-`` start claims: publication counts every Root-issued job by them.
        ident = 'capsule-' + digest(encoded([ledger.grant['run_id'], 'benchmark', self.iteration, self.sha, kind,
                                             fixture['split'], fixture['id'], repeat, role]))[:48]
        sealed = self.sealed(fixture)
        job_fixture = dict(fixture, fixture_set='held_out' if sealed else 'public')
        extra = {'benchmark': {'iteration': self.iteration, 'kind': kind, 'split': fixture['split'],
                               'repeat_index': repeat, 'batch_iterations': batch, 'warmups': warmups,
                               'paired_candidate_sha256': self.sha}}
        ledger._live()
        ledger.halted = True  # Only an observed terminal outcome re-authorizes.
        run = await ledger._run_job(role=role, fixture=job_fixture, candidate_ref=ref, binding_ref=binding_ref,
            ident=ident, index=repeat, node_id=NODE_ID, start_extra=extra,
            make_assets=lambda profile: benchmark_job_assets(self.name, runtime_root=ledger.runtime_root,
                manifest=ledger.manifest, candidate=body, packet=fixture['packet'], iterations=batch,
                warmups=warmups, **profile))
        ledger.halted = False
        receipt = run['receipt']
        wall = receipt.get('wall_time_s')
        need(type(wall) in (int, float) and math.isfinite(wall) and wall > 0, 'BENCHMARK_PROCESS_CLOCK_REQUIRED')
        ran = (receipt.get('termination_reason') == 'completed' and receipt.get('exit_code') == 0
               and receipt.get('observed_runtime') is True
               and not receipt.get('observed_limits', {}).get('admin_output_truncated'))
        observed = observation(completed=False, detail='termination_reason=%s exit_code=%s' % (
            receipt.get('termination_reason'), receipt.get('exit_code')))
        if ran:
            try:
                child, output, error = decode_benchmark_output(run['stdout'])
                need(child['iterations'] == batch and child['warmups'] == warmups, 'BENCHMARK_BATCH_DIFFERS')
                observed = observation(completed=True, input_unmodified=child['input_unmodified'], output=output, error=error)
            except (ValueError, TypeError, KeyError, UnicodeError) as problem:
                observed = observation(completed=False, detail='child framing: ' + str(problem)[:200])
        if not observed['completed'] and receipt.get('stderr_ref'):
            summary = failure_summary(ledger._read(receipt['stderr_ref']), receipt)
            # Withheld cases: exception type only (messages may echo inputs).
            observed['detail'] = summary['exception_type'] if sealed else '%s: %s' % (
                summary['exception_type'], summary['message'][:512])
        evidence = {'schema': EVIDENCE_SCHEMA, 'capsule_name': self.name, 'iteration': self.iteration, 'kind': kind,
            'fixture_id': fixture['id'], 'split': fixture['split'], 'repeat_index': repeat, 'role': role,
            'subject_ref': ref, 'paired_candidate_sha256': self.sha, 'batch_iterations': batch, 'warmups': warmups,
            'bootstrap_schema': BOOTSTRAP_SCHEMA, 'receipt': receipt, 'start_ref': run['start_ref'],
            'input_ref': run['input_ref'], 'program_ref': run['program_ref'], 'wall_s': wall,
            'amortized_wall_s': wall / batch, 'scope': ledger.scope,
            'observation': {'completed': observed['completed'], 'input_unmodified': observed['input_unmodified'],
                            'output_sha256': digest(observed['output']) if isinstance(observed['output'], bytes) else None,
                            # Withheld cases: error type and digest only (messages may echo inputs).
                            'error': observed['error'] if not sealed or observed['error'] is None else {
                                'type': observed['error'].get('type'), 'sha256': digest(encoded(observed['error']))},
                            'detail': observed['detail']}}
        return observed, wall, evidence

    def record(self, evidence, fixture):
        # Every job original is retained in Root captures (publication joins
        # each ref). Withheld inputs/outputs stay sealed: evidence carries only
        # their refs/digests, and redacted error facts.
        self.refs.append(self.ledger.captures.put(evidence))

    async def paired(self, fixture, *, kind, repeat, role, batch, warmups):
        """Run one job; judge a candidate against the paired parent. False stops the run."""
        key = (fixture['split'], fixture['id'])
        observed, wall, evidence = await self.job(fixture, kind=kind, repeat=repeat, role=role, batch=batch, warmups=warmups)
        verdict = None
        if role == 'parent':
            reference = self.parent.setdefault(key, observed)
            same = (reference['completed'], reference['output'], reference['error']) == (
                observed['completed'], observed['output'], observed['error'])
            if not observed['completed'] or not observed['input_unmodified'] or not same:
                verdict = {'passed': False, 'rule': 'parent_reference',
                           'reason': 'parent job failed' if not observed['completed'] else
                           'parent mutated its input' if not observed['input_unmodified'] else
                           'parent output differs between repetitions'}
        else:
            parent = self.parent[key]
            if key not in self.parent_checker and not fixture['malformed'] and parent['completed']:
                self.parent_checker[key] = parent['error'] is None and checker_passes(
                    self.name, fixture['packet'], parent['output'])
            verdict = judge(self.name, fixture, parent, observed, parent_checker_passed=self.parent_checker.get(key))
            if repeat == 0:
                self.cases.append({'id': fixture['id'], 'split': fixture['split'], 'kind': kind,
                                   'withheld': self.sealed(fixture), 'rule': verdict['rule'], 'passed': verdict['passed'],
                                   'improved': verdict.get('improved', False)})
        if verdict is not None:
            evidence['verdict'] = verdict
        self.record(evidence, fixture)
        if verdict is not None and not verdict['passed']:
            self.failure = {'kind': kind, 'fixture_id': fixture['id'], 'split': fixture['split'], 'role': role,
                            'repeat_index': repeat, 'rule': verdict['rule'],
                            'reason': verdict['rule'] if self.sealed(fixture) else verdict['reason']}
            return None
        return wall

    async def semantic(self, version):
        from .capsule_semantic_edges import semantic_edge_fixtures
        fixtures = semantic_edge_fixtures(self.name, version)
        for fixture in fixtures:
            for role in ('parent', 'candidate'):
                if await self.paired(fixture, kind='semantic', repeat=0, role=role, batch=1, warmups=0) is None:
                    return fixtures
        return fixtures


def _semantic_summary(session, fixtures, enabled, version):
    rows = [row for row in session.cases if row['kind'] == 'semantic']
    failed = session.failure is not None and session.failure['kind'] == 'semantic'
    return {'enabled': enabled, 'version': version if enabled else None, 'case_count': len(fixtures),
            'passed': (not failed and len(rows) == len(fixtures)) if enabled else None,
            'parent_checker_discrepancies': sorted(ident for (split, ident), ok in session.parent_checker.items()
                                                   if not ok and split == (fixtures[0]['split'] if fixtures else None))}


async def run_benchmark(ledger, parent_body, candidate_body, *, iteration):
    """``benchmark(parent_body, candidate_body, *, iteration)`` for a dispatcher."""
    need(isinstance(parent_body, bytes) and parent_body == ledger.parent, 'EXACT_BASELINE_PARENT_REQUIRED')
    authorized = _authorize(ledger, candidate_body, iteration)
    name = ledger.grant['capsule_name']
    config = benchmark_config(name, ledger.benchmark_settings)
    plan = execution_plan(name, config)
    semantic_count = 0
    if config['semantic_edges']:
        from .capsule_semantic_edges import semantic_edge_fixtures
        semantic_count = len(semantic_edge_fixtures(name, config['semantic_version']))
    planned = len(plan) + 2 * semantic_count
    sha = authorized['candidate_ref']['sha256']
    claim = digest(encoded([ledger.grant['run_id'], 'benchmark', iteration, sha])) + '.json'
    if (ledger.root / 'claims' / claim).exists():
        raise FileExistsError('BENCHMARK_ALREADY_CLAIMED_NO_REPLAY')
    # The whole call must fit the grant before any job: never a partial benchmark by budget.
    need(ledger.executions + planned <= ledger.grant['max_executions'], 'ROOT_EXECUTION_BUDGET_EXHAUSTED')
    ledger._claim(claim, {
        'grant_ref': ledger.grant_ref, 'kind': 'benchmark', 'iteration': iteration,
        'candidate_ref': authorized['candidate_ref'], 'binding_ref': authorized['binding_ref'], 'planned_jobs': planned})
    session = _Session(ledger, candidate_body, authorized, iteration, 'benchmark')
    semantic_fixtures = await session.semantic(config['semantic_version']) if config['semantic_edges'] else []
    walls = {}
    if session.failure is None:
        for item in plan:
            fixture = item['fixture']
            wall = await session.paired(fixture, kind='timing' if item['timed'] else 'untimed', repeat=item['repeat'],
                                        role=item['role'], batch=item['batch_iterations'], warmups=item['warmups'])
            if wall is None:
                break
            if item['timed']:
                walls[(fixture['id'], item['repeat'], item['role'])] = wall / item['batch_iterations']
    protocol = effective_protocol(name, config)
    timing = timing_batches(name)
    splits = {ident: split for split, row in protocol['splits'].items() for ident in row['timing_case_ids']}
    ids = [ident for row in protocol['splits'].values() for ident in row['timing_case_ids']]
    complete = session.failure is None
    samples = ({ident: [[walls[(ident, r, 'parent')], walls[(ident, r, 'candidate')]] for r in range(config['repetitions'])]
                for ident in ids} if complete else {})
    comparison = (compare_paired_samples(samples, workload_ids=ids, gates=config['gates'],
                      resamples=config['bootstrap_resamples'], seed=config['bootstrap_seed'],
                      confidence=config['confidence'], correctness_passed=True) if complete else None)
    workloads = []
    for ident in ids:
        row = {'id': ident, 'split': splits[ident], 'withheld': splits[ident] in session.withheld,
               'batch_class': timing[ident], 'batch_iterations': config['batch_iterations'][timing[ident]],
               'pairs': len(samples.get(ident, ()))}
        if complete:
            stats = next(item for item in comparison['rows'] if item['id'] == ident)
            row.update(median_ratio=stats['median_ratio'], relative_gain=stats['relative_gain'],
                       regression=stats['regression'],
                       parent_median_s=statistics.median(p for p, _ in samples[ident]),
                       candidate_median_s=statistics.median(c for _, c in samples[ident]))
        workloads.append(row)
    frozen = benchmark_protocol(name)
    gate_results = comparison['gate_results'] if complete else {
        'correctness': False, 'minimum_gain': False, 'ci_upper_bound': False, 'max_workload_regression': False}
    report = {'schema': REPORT_SCHEMA, 'capsule_name': name, 'iteration': iteration, 'scope': ledger.scope,
        'grant_ref': ledger.grant_ref, 'runtime_manifest_ref': ledger.runtime_manifest_ref,
        'parent_ref': ledger.parent_ref, 'candidate_ref': authorized['candidate_ref'],
        'binding_ref': authorized['binding_ref'], 'parent_sha256': ledger.grant['parent_sha256'], 'candidate_sha256': sha,
        'protocol': protocol, 'protocol_sha256': digest(encoded(protocol)),
        'frozen_protocol_sha256': digest(encoded(frozen)), 'frozen_protocol': protocol == frozen,
        'config': config,
        'method': {'paired_order': 'alternating AB BA', 'repetitions': config['repetitions'], 'warmups': config['warmups'],
                   'batch_iterations': config['batch_iterations'],
                   'timing': 'per-process wall / batch iterations (startup, imports, validation, serialization and '
                             'input guard included; checker excluded)',
                   'aggregate': 'equal-weight geometric mean of per-workload median candidate/parent ratios',
                   'interval': 'seeded paired bootstrap over pairs within each workload',
                   'confidence': config['confidence'], 'bootstrap_resamples': config['bootstrap_resamples'],
                   'bootstrap_seed': config['bootstrap_seed']},
        'workloads': workloads, 'samples': samples,
        'median_ratio': comparison['median_ratio'] if complete else None,
        'relative_gain': comparison['relative_gain'] if complete else None,
        'ratio_confidence_interval': comparison['ratio_confidence_interval'] if complete else None,
        'repetitions': config['repetitions'],
        'gates': {key: {'threshold': config['gates'][key], 'passed': gate_results[key]} for key in config['gates']},
        'gate_results': gate_results,
        'correctness_passed': complete, 'objective_met': bool(complete and comparison['objective_met']),
        'correctness': {'contract': CORRECTNESS_CONTRACT, 'passed': complete, 'cases': session.cases,
                        'failure': session.failure},
        'semantic_edges': _semantic_summary(session, semantic_fixtures, config['semantic_edges'], config['semantic_version']),
        'protected_jobs': ledger.executions - session.started, 'planned_jobs': planned,
        'evidence_refs': session.refs, 'model_calls': 0, 'security': 'UNQUALIFIED',
        'admission_ref': None, 'activation_ref': None, 'qualification': protocol.get('qualification')}
    report['summary'] = _summary(report)
    report_ref = ledger.captures.put(report)
    ledger.benchmarks.append(report_ref)
    return {**report, 'report_ref': report_ref}


def _summary(report):
    if not report['correctness_passed']:
        failure = report['correctness']['failure'] or {}
        return 'benchmark stopped: %s case %s (%s) failed %s' % (failure.get('kind'), failure.get('fixture_id'),
                                                                 failure.get('role'), failure.get('rule'))
    low, high = report['ratio_confidence_interval']
    return '%s: %.2f%% faster (ratio %.4f, %d%% CI %.4f-%.4f), objective %s' % (
        report['capsule_name'], 100 * report['relative_gain'], report['median_ratio'],
        round(100 * report['method']['confidence']), low, high, 'met' if report['objective_met'] else 'not met')


async def run_semantic_edges(ledger, candidate_body, *, iteration):
    """The semantic-edge gate alone: parent and candidate once per edge case."""
    from .capsule_semantic_edges import semantic_edge_fixtures
    authorized = _authorize(ledger, candidate_body, iteration)
    name = ledger.grant['capsule_name']
    config = benchmark_config(name, ledger.benchmark_settings)
    need(config['semantic_edges'], 'NO_SEMANTIC_EDGES_CONFIGURED')
    planned = 2 * len(semantic_edge_fixtures(name, config['semantic_version']))
    need(ledger.executions + planned <= ledger.grant['max_executions'], 'ROOT_EXECUTION_BUDGET_EXHAUSTED')
    sha = authorized['candidate_ref']['sha256']
    ledger._claim(digest(encoded([ledger.grant['run_id'], 'semantic-edges', iteration, sha])) + '.json', {
        'grant_ref': ledger.grant_ref, 'kind': 'semantic-edges', 'iteration': iteration,
        'candidate_ref': authorized['candidate_ref'], 'binding_ref': authorized['binding_ref'], 'planned_jobs': planned})
    session = _Session(ledger, candidate_body, authorized, iteration, 'semantic')
    fixtures = await session.semantic(config['semantic_version'])
    report = {'schema': SEMANTIC_REPORT_SCHEMA, 'capsule_name': name, 'iteration': iteration, 'scope': ledger.scope,
        'candidate_ref': authorized['candidate_ref'], 'contract': CORRECTNESS_CONTRACT,
        **_semantic_summary(session, fixtures, True, config['semantic_version']),
        'cases': session.cases, 'failure': session.failure, 'protected_jobs': ledger.executions - session.started,
        'evidence_refs': session.refs, 'model_calls': 0, 'security': 'UNQUALIFIED'}
    report_ref = ledger.captures.put(report)
    return {**report, 'report_ref': report_ref}
