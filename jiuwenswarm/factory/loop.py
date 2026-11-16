"""Durable experiment cycles for the existing agent/controller and quiet supervisor.

The agent selects report-backed hypotheses and operator-admitted templates. This
host reserves budgets, pins a NEW child contract, and delegates execution and
recovery to Benchmark/Jobs. It contains no scheduler or hypothesis chooser.
"""
from __future__ import annotations

import hashlib
from functools import wraps
import fcntl
import json
from pathlib import Path
import time

from . import methodology
from .store import NotFound, ScopeDenied, StaleRevision, TASK_INPUTS, encoded

TERMINAL = {'succeeded', 'failed', 'cancelled'}


def serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        origin = (self.task.get('constraints', {}).get('nonpromoting_diagnostics') or self.task.get('constraints', {}).get('fixed_placement_final_slot') or self.task.get('constraints', {}).get('fixed_placement_screens') or {}).get('origin_task_id', self.task_id)
        name = hashlib.sha256(origin.encode()).hexdigest()
        root = self.store.home / 'loop-locks'
        root.mkdir(exist_ok=True)
        with (root / (name + '.lock')).open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            return method(self, *args, **kwargs)
    return call


class FactoryLoop:
    def __init__(self, store, task_id, *, benchmark=None, clock=time.time):
        if hasattr(store, '_check'):
            store._check(task_id, write=True)
            self.scoped, self.store = store, store._store
        else:
            self.scoped, self.store = store.scoped(task_id), store
        self.task_id, self.clock = task_id, clock
        self.task = self.store.get_task(task_id)
        policy = self.task.get('constraints', {}).get('factory_loop')
        if not isinstance(policy, dict):
            raise ValueError('Operator constraints.factory_loop policy required')
        for key in ('max_cycles', 'max_experiments', 'wall_clock_s'):
            if type(policy.get(key)) is not int or policy[key] <= 0:
                raise ValueError('Loop policy requires positive integer ' + key)
        templates = policy.get('templates')
        if not isinstance(templates, list) or (not templates and not policy.get('experiment_authority')):
            raise ValueError('Operator must admit at least one pinned contract template')
        self.templates = {}
        for item in templates:
            if (not isinstance(item, dict) or set(item) != {'id', 'path', 'sha256', 'allowed_hypothesis_ids'}
                    or not all(isinstance(item[k], str) and item[k] for k in ('id', 'path', 'sha256'))
                    or not isinstance(item['allowed_hypothesis_ids'], list) or not item['allowed_hypothesis_ids']
                    or not all(isinstance(h, str) and h for h in item['allowed_hypothesis_ids'])
                    or item['id'] in self.templates):
                raise ValueError('Templates require unique id, path, sha256 and allowed_hypothesis_ids')
            if len(item['sha256']) != 64 or any(c not in '0123456789abcdef' for c in item['sha256']):
                raise ValueError('Template SHA256 required')
            self.templates[item['id']] = item
        if 'require_branch_binding' in policy and type(policy['require_branch_binding']) is not bool:
            raise ValueError('require_branch_binding must be boolean')
        self.policy = policy
        self.benchmark = benchmark
        with self.store._transaction(inject=False):
            self.store._db.execute('CREATE TABLE IF NOT EXISTS factory_loop_cycles '
                '(task_id TEXT NOT NULL REFERENCES tasks(task_id), cycle_id TEXT NOT NULL, '
                'number INTEGER NOT NULL, record TEXT NOT NULL, PRIMARY KEY(task_id,cycle_id), UNIQUE(task_id,number))')
            self.store._db.execute('CREATE TABLE IF NOT EXISTS factory_loop_policy '
                '(task_id TEXT PRIMARY KEY REFERENCES tasks(task_id), policy TEXT NOT NULL, started REAL NOT NULL, stopped TEXT)')
            self.store._db.execute('INSERT OR IGNORE INTO factory_loop_policy VALUES (?,?,?,NULL)',
                                   (task_id, encoded(policy), self.clock()))
            admitted = self.store._db.execute('SELECT policy FROM factory_loop_policy WHERE task_id=?', (task_id,)).fetchone()
            if admitted['policy'] != encoded(policy):
                raise ValueError('Persisted loop policy cannot be changed by resume')

    def _cycles(self):
        return [json.loads(r['record']) for r in self.store._db.execute(
            'SELECT record FROM factory_loop_cycles WHERE task_id=? ORDER BY number', (self.task_id,))]

    def _get(self, cycle_id):
        for cycle in self._cycles():
            if cycle['cycle_id'] == cycle_id:
                return cycle
        raise NotFound('Loop cycle not found')

    def _write(self, cycle, event):
        """Called inside a transaction; immutable observations retain every change."""
        cycle['event'] = cycle.get('event', 0) + 1
        self.store._db.execute('UPDATE factory_loop_cycles SET record=? WHERE task_id=? AND cycle_id=?',
                              (encoded(cycle), self.task_id, cycle['cycle_id']))
        self.store._insert('observations', dict(task_id=self.task_id,
            obs_id=f"loop:{cycle['number']}:{cycle['event']}", kind='factory_loop',
            values=dict(event=event, cycle=json.loads(encoded(cycle))), source_artifacts=[], error={},
            host_run={}, confidence=None, limitations='Host lifecycle record; not a measured performance claim.', created=self.clock()))

    def _admit(self):
        policy = self.store._db.execute('SELECT * FROM factory_loop_policy WHERE task_id=?', (self.task_id,)).fetchone()
        if policy['stopped']:
            raise ValueError('Loop stopped: ' + policy['stopped'])
        if self.clock() >= policy['started'] + self.policy['wall_clock_s']:
            raise ValueError('Loop wall clock budget exhausted')

    def _diagnostic_admission(self, contract, *, reserving):
        """Explicit continuation preserves a failed A/A and permits screens only."""
        mode = self.task.get('constraints', {}).get('nonpromoting_diagnostics')
        if mode is None:
            return False
        fields = {'origin_task_id','origin_cycle_id','origin_attempt_id',
                  'origin_contract_sha256','origin_manifest_sha256','aggregate_max_experiments'}
        if not isinstance(mode, dict) or set(mode) != fields or mode['aggregate_max_experiments'] != 10:
            raise ScopeDenied('Invalid nonpromoting diagnostic envelope')
        if (contract.get('adapter') != 'strata-benchmark-v3'
                or contract.get('campaign_stage') != 'screen'
                or self.policy['max_experiments'] > 9 or self.policy['max_cycles'] > 9):
            raise ScopeDenied('Nonpromoting diagnostics permit at most nine screen experiments only')
        rows = self.store._db.execute('SELECT record FROM factory_loop_cycles WHERE task_id=? ORDER BY number',
                                     (mode['origin_task_id'],)).fetchall()
        origin_cycles = [json.loads(row['record']) for row in rows]
        matches = [c for c in origin_cycles if c['cycle_id'] == mode['origin_cycle_id']]
        if len(matches) != 1:
            raise ScopeDenied('Diagnostic origin cycle is missing or ambiguous')
        origin = matches[0]
        if (origin['state'] != 'collected' or origin['attempt_id'] != mode['origin_attempt_id']
                or origin['contract_sha256'] != mode['origin_contract_sha256']
                or origin['contract'].get('campaign_stage') != 'aa'):
            raise ScopeDenied('Diagnostic origin ledger identity differs')
        if hashlib.sha256(Path(origin['contract_path']).read_bytes()).hexdigest() != mode['origin_contract_sha256']:
            raise ScopeDenied('Diagnostic origin contract changed')
        attempt = self.store.read(origin['child_task_id'], origin['attempt_id'])
        if (attempt['task_id'] != origin['child_task_id'] or attempt['kind'] != 'lab'
                or attempt['state'] != 'succeeded'
                or attempt['request'].get('contract_sha256') != mode['origin_contract_sha256']
                or attempt['request'].get('contract') != origin['contract']):
            raise ScopeDenied('Diagnostic origin attempt is not verified successful execution')
        raw_root = self.store.home / 'benchmark-spool' / origin['attempt_id']
        if hashlib.sha256((raw_root/'manifest.json').read_bytes()).hexdigest() != mode['origin_manifest_sha256']:
            raise ScopeDenied('Diagnostic origin raw manifest changed')
        from .benchmark import analyze_files
        analysis = analyze_files(origin['contract'], raw_root)
        if (analysis.get('verdict') != 'aa_invalid'
                or analysis.get('verification', {}).get('raw_files_verified') is not True
                or not analysis.get('gates', {}).get('sampled_no_per_question_regression')
                or not analysis.get('gates', {}).get('aa_timing_stable')):
            raise ScopeDenied('Diagnostic continuation requires retained independently verified failed A/A')
        baseline = origin['contract']
        if contract['arms']['A'] != baseline['arms']['A']:
            raise ScopeDenied('Diagnostic baseline profile differs from original A/A')
        for key in ('image','assets','workload','dataset_path','dataset_sha256','execution_sha256','limits','gates',
                    'quality_case_indices','speed_case_indices','runtime_bounds','primary_metric'):
            if contract.get(key) != baseline.get(key):
                raise ScopeDenied('Diagnostic baseline obligation differs: '+key)
        continuation_tasks = []
        for row in self.store._db.execute('SELECT task_id,constraints FROM tasks'):
            constraints = json.loads(row['constraints'])
            if any(constraints.get(key, {}).get('origin_task_id') == mode['origin_task_id'] for key in ('nonpromoting_diagnostics','fixed_placement_final_slot','fixed_placement_screens')):
                continuation_tasks.append(row['task_id'])
        if reserving:
            for task in continuation_tasks:
                for row in self.store._db.execute('SELECT record FROM factory_loop_cycles WHERE task_id=?', (task,)):
                    prior = json.loads(row['record']).get('contract', {})
                    if prior.get('configuration_change') == contract.get('configuration_change'):
                        raise ScopeDenied('Nonpromoting diagnostic settings may not be repeated')
        continuation_cycles = sum(self.store._db.execute(
            'SELECT COUNT(*) FROM factory_loop_cycles WHERE task_id=?', (task,)).fetchone()[0]
            for task in continuation_tasks)
        used = len(origin_cycles) + continuation_cycles + int(reserving)
        if used > mode['aggregate_max_experiments']:
            raise ScopeDenied('Aggregate original plus diagnostic experiment budget exhausted')
        return True

    def _require_qualification(self):
        """Recheck current-task certificates under current package/checker identities."""
        configuration = self.task.get('constraints', {}).get('cc_qualification')
        if configuration is None:
            return []
        policies = configuration.get('policies') if isinstance(configuration, dict) else None
        if (not isinstance(policies, list) or not policies
                or any(not isinstance(p, dict) or not isinstance(p.get('id'), str) for p in policies)
                or len({p['id'] for p in policies}) != len(policies)):
            raise ScopeDenied('Invalid required CC qualification policy')
        from .cc_qualification import assess_admission
        assessments = [json.loads(row['values']) for row in self.store._db.execute(
            'SELECT "values" FROM observations WHERE task_id=? AND kind=? ORDER BY created DESC, obs_id DESC',
            (self.task_id, 'cc_admission_assessment'))]
        proofs = []
        for policy in policies:
            for saved in assessments:
                if not isinstance(saved, dict) or saved.get('policy_id') != policy['id']:
                    continue
                try:
                    # The saved kind/verdict is only a search hint. This repeats
                    # package/module/checker identity and bounded unit checks.
                    result = assess_admission(self.scoped, self.task_id, policy['id'], saved.get('verification_ids'))
                except (ValueError, TypeError, KeyError, NotFound):
                    continue
                if result['eligibility']['verdict'] == 'eligible':
                    proofs.append(result['observation_id'])
                    break
            else:
                raise ScopeDenied('Required CC qualification is missing, blocked or stale: ' + policy['id'])
        return proofs

    def status(self):
        policy = dict(self.store._db.execute('SELECT * FROM factory_loop_policy WHERE task_id=?', (self.task_id,)).fetchone())
        cycles = self._cycles()
        return dict(task_id=self.task_id, started=policy['started'], stopped=policy['stopped'],
            deadline=policy['started'] + self.policy['wall_clock_s'], cycles=cycles,
            remaining_cycles=max(0, self.policy['max_cycles'] - len(cycles)),
            remaining_experiments=max(0, self.policy['max_experiments'] - len(cycles)),
            integration='Agent calls select/execute/collect; existing mission supervisor owns quiet execution.')

    @serialized
    def prepare_experiment(self, experiment_id, specification, image):
        self._admit()
        from .experiments import prepare
        return prepare(self, experiment_id, specification, image)

    @serialized
    def prepare_comparison(self, comparison_id, source_cycle_id, template_id):
        self._admit()
        from .construction_comparison import prepare
        return prepare(self, comparison_id, source_cycle_id, template_id)

    @serialized
    def select(self, cycle_id, evidence_ids, hypothesis_id, template_id=None, expected_rev=None, branch_id=None, expected_graph_rev=None, experiment_id=None, comparison_id=None):
        """Reserve one cycle before any external effect; agent makes both choices."""
        if type(expected_rev) is not int or expected_rev < 0:
            raise ValueError('expected_rev must be a nonnegative integer')
        if not isinstance(cycle_id, str) or not cycle_id or len(cycle_id) > 100:
            raise ValueError('Bounded nonempty cycle_id required')
        if sum(v is not None for v in (template_id,experiment_id,comparison_id)) != 1:
            raise ValueError('Select exactly one template, prepared experiment or comparison')
        request = dict(evidence_ids=evidence_ids, hypothesis_id=hypothesis_id,
                       template_id=template_id, expected_rev=expected_rev)
        if comparison_id is not None:
            request['comparison_id'] = comparison_id
        if experiment_id is not None:
            request['experiment_id'] = experiment_id
        if (branch_id is None) != (expected_graph_rev is None):
            raise ValueError('branch_id and expected_graph_rev must be supplied together')
        if branch_id is not None:
            if not isinstance(branch_id, str) or not branch_id.strip():
                raise ValueError('Nonempty branch_id required')
            if type(expected_graph_rev) is not int or expected_graph_rev < 0:
                raise ValueError('expected_graph_rev must be a nonnegative integer')
            request.update(branch_id=branch_id, expected_graph_rev=expected_graph_rev)
        if comparison_id is not None:
            from .construction_comparison import resolve, stage_admission
            contract, template = resolve(self,comparison_id)
            if hypothesis_id != contract['hypothesis']:
                raise ScopeDenied('Comparison hypothesis must match independent admission')
            stage_admission(self,contract)
            analysis = dict(candidate=dict(hypothesis=hypothesis_id,reason='Separately admitted source comparison'))
        elif experiment_id is not None:
            from .experiments import resolve
            contract, template = resolve(self, experiment_id)
            spec = contract['specification']
            if evidence_ids != spec['evidence_ids'] or hypothesis_id != spec['hypothesis']:
                raise ScopeDenied('Selection must preserve prepared hypothesis and evidence')
            analysis = dict(candidate=dict(hypothesis=spec['hypothesis'], reason=spec['interpretation']))
        else:
            analysis = methodology.dispatch(self.scoped, self.task_id, 'ablation',
                dict(evidence_ids=evidence_ids, hypothesis_id=hypothesis_id))['analysis']
            if template_id not in self.templates:
                raise ScopeDenied('Contract template is outside operator policy')
            template = self.templates[template_id]
            if hypothesis_id not in template['allowed_hypothesis_ids']:
                raise ScopeDenied('Hypothesis is not admitted for this contract template')
            raw = Path(template['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != template['sha256']:
                raise ValueError('Admitted template identity changed')
            contract = validate_loop_contract(json.loads(raw))
        # Template is the complete permitted treatment envelope in v1; no arbitrary
        # parameters, source, image, data, gates or workloads can be supplied here.
        if contract.get('target') != 'spark-gb10':
            raise ValueError('Unsupported loop target')
        qualification_ids = self._require_qualification()
        decision_evidence = list(dict.fromkeys([*evidence_ids, *qualification_ids]))
        with self.store._transaction():
            existing = next((c for c in self._cycles() if c['cycle_id'] == cycle_id), None)
            if existing:
                if existing['request'] != request:
                    raise ValueError('cycle_id replay conflicts with original selection')
                return existing
            branch_binding = self._bind_branch(branch_id, expected_graph_rev, hypothesis_id, contract)
            if contract.get('adapter') == 'strata-benchmark-v5':
                from .fixed_screen_benchmark import admit_fixed_screens
                admit_fixed_screens(self,contract,reserving=True)
            if contract.get('adapter') == 'strata-benchmark-v4':
                from .fixed_placement_benchmark import admit_final_slot
                admit_final_slot(self,contract,reserving=True)
            if contract.get('adapter') == 'strata-benchmark-v3':
                cycles = self._cycles()
                diagnostic = self._diagnostic_admission(contract, reserving=True)
                if not diagnostic and not cycles and contract['campaign_stage'] != 'aa':
                    raise ScopeDenied('Broad campaign requires independent A/A first')
                if not diagnostic and cycles and contract['campaign_stage'] == 'aa':
                    raise ScopeDenied('A/A may run only as the first broad experiment')
                if not diagnostic and cycles and cycles[0].get('result', {}).get('analysis', {}).get('verdict') != 'aa_valid':
                    raise ScopeDenied('Broad treatment requires collected valid independent A/A')
                if not diagnostic and contract['campaign_stage'] == 'confirm' and not any(
                        c['contract'].get('campaign_stage') == 'screen'
                        and c['contract'].get('configuration_change') == contract['configuration_change']
                        and c.get('result', {}).get('analysis', {}).get('verdict') == 'screen_candidate'
                        for c in cycles):
                    raise ScopeDenied('Confirmation requires a qualifying same-treatment screen')
            self._admit()
            cycles = self._cycles()
            if any(c['state'] != 'collected' for c in cycles):
                raise ValueError('Collect the pending cycle before selecting another')
            if len(cycles) >= min(self.policy['max_cycles'], self.policy['max_experiments']):
                raise ValueError('Loop cycle/experiment budget exhausted')
            if self.store.get_task(self.task_id)['current_decision_rev'] != expected_rev:
                raise StaleRevision('Decision changed before cycle selection')
            number = len(cycles) + 1
            # The deterministic decision and cycle reservation commit together.
            self.store.validate_evidence(self.task_id, decision_evidence, getattr(self.scoped, 'readable', ()))
            decision = dict(decision_id=f'{self.task_id}:decision:{expected_rev + 1}', task_id=self.task_id,
                rev=expected_rev + 1, parent_rev=expected_rev, evidence_ids=decision_evidence,
                observations=[analysis], hypothesis=analysis['candidate']['hypothesis'],
                uncertainty=analysis['candidate']['reason'], action=dict(type='measure', cycle_id=cycle_id,
                capability='factory_loop.execute', template_id=template_id), expected_evidence='Pinned benchmark result plus bounded follow-up proposal',
                budget=dict(max_experiments=1), stop_condition='Correctness failure, incomplete evidence, cancellation or exhausted policy',
                reason_for_change='Agent selected a report-backed hypothesis under the admitted template envelope', created=self.clock())
            self.store._insert('decisions', decision)
            self.store._db.execute('UPDATE tasks SET current_decision_rev=? WHERE task_id=?', (expected_rev + 1, self.task_id))
            cycle = dict(cycle_id=cycle_id, number=number, request=request, state='selected',
                decision_rev=expected_rev + 1, template_sha256=template['sha256'],
                child_task_id=f'{self.task_id}-loop-{number}', idem_key=f'factory-loop-{number}',
                attempt_id=None, contract=contract, qualification_ids=qualification_ids, created=self.clock())
            if branch_binding is not None:
                cycle['branch_binding'] = branch_binding
                from .taskgraph import _apply_patch
                _apply_patch(self.store, self.task_id, {'update': [dict(node_id=branch_id, state='running',
                    reason='Agent-selected admitted experiment reserved; no execution or acceptance implied.')]},
                    expected_graph_rev, decision['rev'])
            self.store._db.execute('INSERT INTO factory_loop_cycles VALUES (?,?,?,?)',
                (self.task_id, cycle_id, number, encoded(cycle)))
            self._write(cycle, 'selected')
        return cycle

    def _bind_branch(self, branch_id, expected_graph_rev, hypothesis_id, contract):
        if branch_id is None:
            if self.policy.get('require_branch_binding') is True:
                raise ScopeDenied('This loop requires an explicit branch binding')
            return None
        from .taskgraph import plan_get
        graph = plan_get(self.store, self.task_id)
        if graph['rev'] != expected_graph_rev:
            raise StaleRevision('Branch graph changed before cycle selection')
        nodes = {n['node_id']: n for n in graph['nodes']}
        node = nodes.get(branch_id)
        if node is None or 'branch' not in node or branch_id not in graph['ready_frontier']:
            raise ScopeDenied('Branch must be ready in the current task')
        if node['branch']['hypothesis'] != hypothesis_id:
            raise ScopeDenied('Branch hypothesis must match the selected hypothesis ID')
        if any(c.get('branch_binding', {}).get('node_id') == branch_id for c in self._cycles()):
            raise ScopeDenied('Branch already has an experiment; refine into a new branch')
        # Both supported submitters add 120 seconds to the campaign worker bound.
        # This is a conservative allocation, not measured device/CPU consumption.
        worker_bound = contract['campaign_timeout_s'] + 120
        if node['branch']['allocation']['gpu_seconds'] < worker_bound:
            raise ScopeDenied('Branch GPU reservation must cover campaign timeout plus worker margin')
        return dict(node_id=branch_id, selected_graph_rev=graph['rev'],
                    hypothesis_id=hypothesis_id, worker_bound_s=worker_bound)

    def _check_branch_dispatch(self, cycle):
        binding = cycle.get('branch_binding')
        if binding is None:
            return
        from .taskgraph import dispatch_precondition
        dispatch_precondition(self.store, self.task_id, binding['node_id'])

    def _finish_branch(self, cycle, evidence_id):
        binding = cycle.get('branch_binding')
        if binding is None:
            return
        from .taskgraph import plan_get, _apply_patch
        graph = plan_get(self.store, self.task_id)
        node = next(n for n in graph['nodes'] if n['node_id'] == binding['node_id'])
        # A prune is not undone by late results. The ledger/status still exposes them.
        if node['state'] in {'cancelled', 'superseded'}:
            return
        branch = dict(node['branch'])
        if not branch.get('measurement_evidence_id'):
            branch['stage'] = 'inconclusive'
        _apply_patch(self.store, self.task_id, {'update': [dict(node_id=node['node_id'],
            state='done', evidence_ids=[evidence_id], branch=branch,
            outcome='Experiment collected; inspect scoped evidence before any acceptance decision.')]},
            graph['rev'], cycle['decision_rev'])

    def _manager(self, cycle):
        if self.benchmark is not None:
            return self.benchmark  # injected adapter is for offline durability tests
        if cycle['contract'].get('adapter') == 'factory-experiment-v1':
            from .experiment_jobs import ExperimentJobs
            return ExperimentJobs(self.store)
        if cycle['contract'].get('adapter') == 'strata-prefill-scoped-v1':
            from .prefill_workbench import Workbench
            return Workbench(self.store)
        from .benchmark import Benchmark
        return Benchmark(self.store)

    @serialized
    def execute(self, cycle_id):
        cycle = self._get(cycle_id)
        from .execution_binding import verify_task
        binding_id = verify_task(self.store, self.task_id)
        if binding_id is not None:
            if cycle['contract'].get('adapter') == 'factory-experiment-v1' and cycle['contract']['execution_binding_id'] != binding_id:
                raise ScopeDenied('Prepared experiment requires its original execution binding; prepare a new revision')
            cycle['execution_binding_id'] = binding_id
        if cycle['state'] in {'submitted', 'collected'}:
            return cycle
        if cycle['contract'].get('adapter') == 'strata-construction-v1':
            from .construction_comparison import resolve
            current,_ = resolve(self,cycle['request']['comparison_id'])
            if current != cycle['contract']: raise ValueError('Comparison policy changed before dispatch')
        # Existing Jobs keys reconcile a crash after queue submission, including
        # recovery after deadline. A fresh external effect always needs budget.
        prior = self.store._db.execute('SELECT attempt_id FROM attempts WHERE task_id=? AND idem_key=?',
            (cycle['child_task_id'], cycle['idem_key'])).fetchone()
        build_prior = self.store._db.execute('SELECT attempt_id FROM attempts WHERE task_id=? AND idem_key=?',
            (self.task_id, cycle['idem_key'] + '-build')).fetchone()
        if not build_prior:
            build_prior = self.store._db.execute('SELECT attempt_id FROM builder_reuse_keys WHERE task_id=? AND idem_key=?',
                (self.task_id, cycle['idem_key'] + '-build')).fetchone()
        if not prior and not build_prior:
            self._check_branch_dispatch(cycle)
            if cycle['contract'].get('adapter') == 'strata-benchmark-v5':
                from .fixed_screen_benchmark import admit_fixed_screens
                admit_fixed_screens(self,cycle['contract'],reserving=False)
            if cycle['contract'].get('adapter') == 'strata-benchmark-v4':
                from .fixed_placement_benchmark import admit_final_slot
                admit_final_slot(self,cycle['contract'],reserving=False)
            self._diagnostic_admission(cycle['contract'], reserving=False)
            self._admit()
        if cycle['contract'].get('build_binding') is not None:
            from .experiment_build import ensure_build
            cycle, ready = ensure_build(self, cycle)
            if not ready:
                return cycle
        if not prior:
            # Reconciliation may finish an existing build after stop/deadline,
            # but a new lab effect still requires current admission.
            self._check_branch_dispatch(cycle)
            self._admit()
        artifact_id = f"loop-contract:{cycle['number']}"
        raw = (json.dumps(cycle['contract'], indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
        try:
            artifact = self.store.read(self.task_id, artifact_id)
        except NotFound:
            artifact = self.store.put_artifact(self.task_id, artifact_id, raw, 'application/json', None)
        digest = hashlib.sha256(raw).hexdigest()
        if artifact['sha256'] != digest:
            raise ValueError('Frozen child contract identity changed')
        path = str(self.store.home / artifact['location'])
        child_id = cycle['child_task_id']
        parent = self.store.get_task(self.task_id)
        child = dict(task_id=child_id, objective=parent['objective'], target=parent['target'],
            allowed_effects=parent['allowed_effects'], budget=parent['budget'],
            constraints=parent['constraints'] | dict(benchmark_contract_sha256=digest,
                factory_loop_parent=self.task_id), contract_id=path)
        runtime_binding = None
        if cycle['contract'].get('adapter') == 'factory-experiment-v1':
            from .execution_binding import digest as identity_digest
            base_binding = parent['constraints']['execution_binding']
            runtime_binding = dict(format='factory-runtime-execution/1',
                factory_binding_id=base_binding['binding_id'],package_release=base_binding['release'],
                backend_sha256=base_binding['backend']['sha256'],components=base_binding['components'],
                runtime_image=cycle['contract']['image'],experiment_sha256=digest,
                build_receipt_sha256=cycle.get('build_receipt_sha256'))
            runtime_binding['binding_id'] = identity_digest(runtime_binding)
            child['constraints']['runtime_execution_binding'] = runtime_binding
        child['constraints'].pop('factory_loop', None)
        for key in TASK_INPUTS:
            if key not in child and key in parent:
                child[key] = parent[key]
        try:
            saved = self.store.get_task(child_id)
            if saved['contract_id'] != path or saved['constraints'] != child['constraints']:
                raise ValueError('Loop child task identity conflicts')
        except NotFound:
            self.store.create_task(child)
        with self.store._transaction():
            cycle = self._get(cycle_id)
            if cycle['state'] in {'submitted', 'collected'}:
                return cycle
            cycle.update(state='dispatching', contract_path=path, contract_sha256=digest)
            if runtime_binding is not None:
                cycle['runtime_execution_binding']=runtime_binding
            self._write(cycle, 'dispatch_intent')
        attempt = self._manager(cycle).submit(child_id, path, cycle['idem_key'])
        with self.store._transaction():
            cycle = self._get(cycle_id)
            cycle.update(state='submitted', attempt_id=attempt['attempt_id'])
            self._write(cycle, 'submitted')
        return cycle

    @serialized
    def collect(self, cycle_id):
        cycle = self._get(cycle_id)
        if cycle['state'] == 'collected':
            return cycle
        if cycle['state'] != 'submitted':
            raise ValueError('Execute/recover the cycle before collecting')
        result = self._manager(cycle).result(cycle['child_task_id'], cycle['attempt_id'])
        if result['state'] not in TERMINAL:
            return dict(cycle, pending_result=result)
        # Retain failures and null results as evidence; never silently rerun them.
        report = result.get('analysis') or dict(status=result['state'], error='No analysis available')
        report = dict(report)
        if cycle['contract'].get('adapter') == 'factory-experiment-v1':
            attempt = self.store.read(cycle['child_task_id'],cycle['attempt_id'])
            artifacts = []
            for source_id in attempt.get('result_refs',[]):
                source = self.store.read(cycle['child_task_id'],source_id)
                if 'sha256' not in source:
                    continue
                artifact_id = f"loop-artifact:{cycle['number']}:" + source_id.split(':',1)[-1]
                try:
                    retained = self.store.read(self.task_id,artifact_id)
                    if retained['sha256'] != source['sha256']:
                        raise ValueError('Collected artifact identity conflicts')
                except NotFound:
                    retained = self.store.put_artifact(self.task_id,artifact_id,
                        self.store.artifact_bytes(cycle['child_task_id'],source_id),source['media_type'],None)
                artifacts.append(dict(artifact_id=artifact_id,sha256=retained['sha256'],
                                      source_task_id=cycle['child_task_id'],source_artifact_id=source_id))
            report['raw_artifacts'] = artifacts
            from .experiment_jobs import evidence_complete
            report['verified_complete'] = evidence_complete(report)
            report['promotion_authorized'] = False
        if cycle['contract'].get('adapter') == 'strata-construction-v1':
            report['verified_complete'] = (report.get('verification',{}).get('raw_files_verified') is True
                and report.get('verification',{}).get('complete_cells') == len(cycle['contract']['order']))
        report.setdefault('status', result['state'])
        evidence_id = f"loop-result:{cycle['number']}"
        try:
            self.store.read(self.task_id, evidence_id)
        except NotFound:
            self.store.append_observation(self.task_id, dict(obs_id=evidence_id, kind='factory_loop_result',
                values=report, host_run=dict(child_task_id=cycle['child_task_id'], attempt_id=cycle['attempt_id']),
                limitations='Child benchmark analysis; original child evidence remains retained.'))
        if cycle['contract'].get('adapter') == 'strata-construction-v1':
            from .construction_comparison import record_evaluation
            record_evaluation(self,cycle,report,evidence_id)
        followup = (dict(status='evidence_ready' if report.get('verified_complete') else 'incomplete_evidence',
                         evidence_ids=[evidence_id], verified_complete=report.get('verified_complete', False), promotion_authorized=False)
                    if cycle['contract'].get('adapter') in {'factory-experiment-v1','strata-construction-v1'} else
                    methodology.dispatch(self.scoped, self.task_id, 'followup', dict(evidence_ids=[evidence_id]))['analysis'])
        with self.store._transaction():
            cycle = self._get(cycle_id)
            if cycle['state'] != 'collected':
                self._finish_branch(cycle, evidence_id)
                cycle.update(state='collected', result=result, evidence_id=evidence_id,
                             followup=followup, ended=self.clock())
                self._write(cycle, 'collected')
        return cycle

    @serialized
    def abandon(self, cycle_id, reason):
        """Close a reservation that has never submitted; do not refund its budget."""
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise ValueError('Bounded nonempty abandonment reason required')
        with self.store._transaction():
            cycle = self._get(cycle_id)
            if cycle.get('abandoned_reason') is not None:
                if cycle['abandoned_reason'] != reason:
                    raise ValueError('Abandon replay conflicts with original reason')
                return cycle
            prior = self.store._db.execute('SELECT attempt_id FROM attempts WHERE task_id=? AND idem_key=?',
                (cycle['child_task_id'], cycle['idem_key'])).fetchone()
            build_prior = self.store._db.execute('SELECT attempt_id FROM attempts WHERE task_id=? AND idem_key=?',
                (self.task_id, cycle['idem_key'] + '-build')).fetchone()
            if not build_prior:
                build_prior = self.store._db.execute('SELECT attempt_id FROM builder_reuse_keys WHERE task_id=? AND idem_key=?',
                    (self.task_id, cycle['idem_key'] + '-build')).fetchone()
            if prior or build_prior or cycle['state'] not in {'selected', 'dispatching'}:
                raise ScopeDenied('Recover/collect an existing attempt; abandonment cannot hide submitted work')
            report = dict(status='not_executed', reason=reason, measured=False)
            evidence_id = f"loop-abandoned:{cycle['number']}"
            self.store._insert('observations', dict(task_id=self.task_id, obs_id=evidence_id,
                kind='factory_loop_result', values=report, source_artifacts=[], error={}, host_run={},
                confidence=None, limitations='Unsubmitted reservation closed; no budget refund or measurement.', created=self.clock()))
            self._finish_branch(cycle, evidence_id)
            cycle.update(state='collected', abandoned_reason=reason, evidence_id=evidence_id,
                result=dict(state='cancelled', analysis=report), ended=self.clock(),
                followup=dict(status='proposal_only', requires_operator_admission=True))
            self._write(cycle, 'abandoned_before_submission')
        return cycle

    @serialized
    def stop(self, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError('Stop reason required')
        with self.store._transaction():
            previous = self.store._db.execute('SELECT stopped FROM factory_loop_policy WHERE task_id=?', (self.task_id,)).fetchone()['stopped']
            if previous is None:
                self.store._db.execute('UPDATE factory_loop_policy SET stopped=? WHERE task_id=?', (reason, self.task_id))
                self.store._insert('observations', dict(task_id=self.task_id, obs_id='factory-loop-stop',
                    kind='factory_loop_stop', values=dict(reason=reason), source_artifacts=[], error={},
                    host_run={}, confidence=None, limitations='Stop intent prevents new dispatch; existing jobs remain retained.', created=self.clock()))
        return self.status()


def validate_loop_contract(contract):
    """Admit only existing bounded adapter contracts, never arbitrary modules."""
    if contract.get('adapter') == 'factory-experiment-v1':
        from .experiments import validate_contract
    elif contract.get('adapter') == 'strata-prefill-scoped-v1':
        from .prefill_workbench import validate_contract
    else:
        from .benchmark import validate_contract
    return validate_contract(contract)


def owned_attempts(store, task_id):
    """Parent plus ledger-bound children; labels alone never establish ownership."""
    tasks = [task_id]
    exists = store._db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='factory_loop_cycles'").fetchone()
    if exists:
        tasks += [json.loads(row['record'])['child_task_id'] for row in store._db.execute(
            'SELECT record FROM factory_loop_cycles WHERE task_id=?', (task_id,))]
    placeholders = ','.join('?' for _ in tasks)
    return [store._decode('attempts', row) for row in store._db.execute(
        f'SELECT * FROM attempts WHERE task_id IN ({placeholders})', tasks)]


def dispatch(store, task_id, operation, inputs):
    methods = {'status': set(), 'select': {'cycle_id', 'evidence_ids', 'hypothesis_id', 'expected_rev'},
               'prepare_experiment': {'experiment_id', 'specification', 'image'},
               'prepare_comparison': {'comparison_id', 'source_cycle_id', 'template_id'},
               'execute': {'cycle_id'}, 'collect': {'cycle_id'}, 'abandon': {'cycle_id', 'reason'}, 'stop': {'reason'}}
    optional = {'branch_id', 'expected_graph_rev', 'template_id', 'experiment_id', 'comparison_id'} if operation == 'select' else set()
    if (operation not in methods or not isinstance(inputs, dict)
            or set(inputs) - (methods[operation] | optional) or methods[operation] - set(inputs)):
        raise ValueError('Invalid factory loop operation or input fields')
    return {'result': getattr(FactoryLoop(store, task_id), operation)(**inputs)}
