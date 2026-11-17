"""Durable native-CC execution for the dynamical workflow composition model.

SQLite owns graph revisions/events only. The CC host owns calls; Lab Manager
owns jobs, resource budgets, cleanup and scientific verdicts. tick() is bounded:
it dispatches ready leaves and reconciles submitted work without busy waiting.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from .cc_catalog import Capability
from .interconnect import VERSION, select, assemble


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


class WorkflowConflict(ValueError):
    pass


class CCWorkflow:
    def __init__(self, root, host, capabilities, *, task_id, grants=(), max_nodes=128,
                 deadline=None, context=None, interconnect=None):
        if interconnect not in {None, VERSION}:
            raise ValueError('Unsupported interconnect version')
        self.interconnect = interconnect
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.host = host
        self.capabilities = {cap.id: cap for cap in capabilities}
        if len(self.capabilities) != len(capabilities) or any(not isinstance(c, Capability) for c in capabilities):
            raise ValueError('Workflow leaves must be unique native CC capabilities')
        if not task_id or not 0 < max_nodes <= 4096:
            raise ValueError('Task identity and bounded graph size required')
        self.task_id, self.grants = task_id, sorted(set(grants))
        self.max_nodes, self.deadline = max_nodes, deadline
        # Host-supplied task context is bound into every run. Callers must not
        # source grants, store paths or task context from a workflow request.
        self.context = deepcopy(context or {})
        identity = dict(task=task_id, grants=self.grants, context=self.context,
            host=str(host.store), capabilities=[c.serializable(include_contracts=interconnect is not None) for c in capabilities],
            max_nodes=max_nodes, deadline=deadline)
        if interconnect:
            identity['interconnect'] = interconnect
        self.identity = digest(identity)
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS events (run TEXT, seq INTEGER, body TEXT, PRIMARY KEY(run,seq))')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.root / 'workflows.sqlite', timeout=60)
        try:
            db.execute('PRAGMA synchronous=FULL')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _get(self, db, run_id):
        if any(os.environ.get(key, '') != value for key, value in self.context.get('environment', {}).items()):
            raise WorkflowConflict('Task execution environment changed; use its original scoped process')
        row = db.execute('SELECT body FROM runs WHERE id=?', (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        run = json.loads(row[0])
        if run['identity'] != self.identity:
            raise WorkflowConflict('Workflow task, authority, releases or host context changed')
        return run

    def get(self, run_id):
        with self.db() as db:
            return self._get(db, run_id)

    def events(self, run_id, after=0):
        with self.db() as db:
            self._get(db, run_id)
            return [json.loads(row[0]) for row in db.execute(
                'SELECT body FROM events WHERE run=? AND seq>? ORDER BY seq', (run_id, after))]

    def _save(self, db, run, event, **details):
        run['sequence'] += 1
        record = dict(sequence=run['sequence'], type=event, time=time.time(), **details)
        db.execute('INSERT INTO events VALUES (?,?,?)', (run['id'], run['sequence'], encoded(record)))
        db.execute('INSERT OR REPLACE INTO runs VALUES (?,?)', (run['id'], encoded(run)))

    def _reference(self, ref, graph, available):
        if (ref.channel != 'outputs' or ref.pointer or ref.assemble is not None) and self.interconnect != VERSION:
            raise ValueError('Extended bindings require ' + VERSION)
        if ref.node_id is None:
            if ref.channel != 'outputs':
                raise ValueError('External inputs have no completion channel')
            kind = graph.inputs.get(ref.port)
        else:
            cap = available.get(ref.node_id)
            ports = (cap.outputs if ref.channel == 'outputs' else
                     {name: spec['kind'] for name, spec in cap.result_contracts.items()}) if cap else {}
            kind = ports.get(ref.port)
        if kind is None or (ref.pointer and kind != 'json') or (not ref.pointer and ref.assemble is None and kind != ref.kind):
            raise ValueError('Invalid or forward workflow port binding')

    @staticmethod
    def _value(binding, by_id):
        if 'value' in binding:
            value = binding['value']
        else:
            node = by_id[binding['node']]
            channel = 'completion_outputs' if binding.get('channel') == 'result' else 'outputs'
            try:
                value = node[channel][binding['port']]
            except KeyError as error:
                raise ValueError('Interconnect source port is unavailable') from error
        return assemble(select(value, binding.get('pointer', '')), binding.get('assemble'))

    def _nodes(self, graph, inputs, existing=()):
        if set(inputs) != set(graph.inputs):
            raise ValueError('Workflow external input ports differ')
        available = {n['id']: self.capabilities[n['capability']] for n in existing}
        nodes = []
        for node in graph.nodes:
            if node.id in available or node.stage_id not in self.capabilities:
                raise ValueError('Duplicate node or unselected capability')
            cap = self.capabilities[node.stage_id]
            if set(cap.changes) - set(self.grants):
                raise ValueError('Workflow exceeds operator grants')
            if set(cap.inputs) - cap.optional_inputs - set(node.input_bindings) or set(node.input_bindings) - set(cap.inputs):
                raise ValueError('Capability input ports differ')
            bindings = {}
            for name, ref in node.input_bindings.items():
                self._reference(ref, graph, available)
                if ref.kind != cap.inputs[name]:
                    raise ValueError('Capability input kind differs')
                value = dict(value=inputs[ref.port]) if ref.node_id is None else dict(node=ref.node_id, port=ref.port)
                if ref.channel != 'outputs':
                    value['channel'] = ref.channel
                if ref.pointer:
                    value['pointer'] = ref.pointer
                if ref.assemble is not None:
                    value['assemble'] = ref.assemble
                if ref.node_id is None and self.interconnect:
                    self.host.validate_value(cap.input_contracts.get(name, {'kind': cap.inputs[name]}), self._value(value, {}))
                bindings[name] = value
            nodes.append(dict(id=node.id, path=node.workflow_path, capability=cap.id,
                release=cap.release, inputs=bindings, state='pending', outputs={}, receipts=[], lab=None,
                operation=None, polls=0, last_tick=0))
            available[node.id] = cap
        if len(available) > self.max_nodes:
            raise ValueError('Workflow node budget exceeded')
        for ref in graph.outputs.values():
            self._reference(ref, graph, available)
        return nodes

    def create(self, graph, inputs, *, objective, run_id=None):
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError('An explicit engineering objective is required')
        request = dict(graph=graph.serializable(), inputs=inputs, objective=objective)
        run_id = run_id or str(uuid.uuid4())
        if not isinstance(run_id, str) or not run_id or len(run_id) > 128:
            raise ValueError('Invalid run identity')
        nodes = self._nodes(graph, inputs)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM runs WHERE id=?', (run_id,)).fetchone():
                run = self._get(db, run_id)
                if run['request_digest'] != digest(request):
                    raise WorkflowConflict('Run identity reused with different inputs')
                return run
            run = dict(id=run_id, task_id=self.task_id, identity=self.identity, objective=objective,
                request_digest=digest(request), status='ready', revision=1, sequence=0,
                created_at=time.time(), nodes=nodes, stopping=False, stop_reason=None,
                acceptance='not_assessed', outputs={}, revisions=[dict(revision=1, graph=request['graph'], inputs=deepcopy(inputs))])
            if self.interconnect:
                run['interconnect'] = self.interconnect
            self._save(db, run, 'workflow.created', revision=1, nodes=deepcopy(nodes))
            return run

    def append(self, run_id, graph, inputs, *, expected_revision, decision):
        """Agent-directed adaptation. Existing calls/evidence are never rewritten."""
        if not isinstance(decision, dict) or not decision.get('reason') or not decision.get('evidence'):
            raise ValueError('Adaptation requires a reason and scoped evidence references')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            run = self._get(db, run_id)
            if run['revision'] != expected_revision or run['stopping']:
                raise WorkflowConflict('Stale graph revision or stopped workflow')
            for ref in decision['evidence']:
                if not isinstance(ref, dict) or ref.get('task_id') != self.task_id or not ref.get('node_id'):
                    raise ValueError('Evidence must identify this task and a collected node')
                found = next((n for n in run['nodes'] if n['id'] == ref['node_id']), None)
                if not found or found['state'] not in {'completed', 'failed'} or not found['receipts']:
                    raise ValueError('Adaptation evidence is not collected')
            nodes = self._nodes(graph, inputs, run['nodes'])
            run['nodes'].extend(nodes)
            run['revision'] += 1
            run['status'] = 'ready'
            run['revisions'].append(dict(revision=run['revision'], graph=graph.serializable(), inputs=deepcopy(inputs), decision=decision))
            self._save(db, run, 'workflow.revised', revision=run['revision'], decision=decision, nodes=deepcopy(nodes))
            return run

    def stop(self, run_id, reason='operator_stop'):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            run = self._get(db, run_id)
            run.update(stopping=True, stop_reason=run['stop_reason'] or reason, status='stopping')
            self._save(db, run, 'workflow.stop_requested', reason=run['stop_reason'])
            return run

    def _claim(self, run_id):
        # Persist exact call intent before touching the CC host. A second process
        # can recover this intent; Host.call's unique key prevents double effects.
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            run = self._get(db, run_id)
            if self.deadline is not None and time.time() >= self.deadline:
                run.update(stopping=True, stop_reason=run['stop_reason'] or 'deadline')
            by_id = {node['id']: node for node in run['nodes']}
            for node in sorted(run['nodes'], key=lambda n: n['last_tick']):
                cap = self.capabilities[node['capability']]
                if node['operation']:
                    node['last_tick'] = run['sequence'] + 1
                    self._save(db, run, 'cc.reconcile', node_id=node['id'])
                    return run, node, node['operation']
                if node['state'] in {'completed', 'failed', 'cancelled', 'blocked'}:
                    continue
                if node['lab']:
                    operation = cap.lifecycle['cancel' if run['stopping'] else 'status']
                    inputs = {'attempt_id': node['lab']['attempt_id']}
                    phase = 'cancel' if run['stopping'] else 'status'
                    node['polls'] += 1
                elif node['state'] == 'unknown':
                    # A call without a returned job identity is not safe to retry
                    # under a new key. Retain it until the host is reconciled.
                    operation, inputs, phase = cap.capability, node['resolved_inputs'], 'call'
                elif run['stopping']:
                    node['state'] = 'cancelled'
                    continue
                else:
                    parents = [by_id[value['node']] for value in node['inputs'].values() if 'node' in value]
                    if any(parent['state'] in {'failed', 'cancelled', 'blocked'} for parent in parents):
                        node['state'] = 'blocked'
                        continue
                    if any(parent['state'] != 'completed' for parent in parents):
                        continue
                    try:
                        inputs = {name: self._value(value, by_id) for name, value in node['inputs'].items()}
                        if self.interconnect:
                            for name, value in inputs.items():
                                self.host.validate_value(cap.input_contracts.get(name, {'kind': cap.inputs[name]}), value)
                    except ValueError:
                        node.update(state='failed', error='interconnect_contract_mismatch')
                        self._save(db, run, 'interconnect.rejected', node_id=node['id'])
                        continue
                    if cap.lifecycle:
                        # One durable job key per graph leaf; caller-selected keys
                        # cannot make unrelated branches share an attempt.
                        inputs['idem_key'] = 'wf-' + digest([run_id, node['id']])
                    node['resolved_inputs'] = inputs
                    operation, phase = cap.capability, 'call'
                key = 'wf-' + digest([run_id, node['id'], phase, 0 if phase == 'call' else node['polls']])
                intent = dict(capability=operation, inputs=inputs, key=key, phase=phase)
                node['operation'] = intent
                node['last_tick'] = run['sequence'] + 1
                node['state'] = 'calling' if phase == 'call' else 'waiting'
                self._save(db, run, 'cc.intent', node_id=node['id'], intent=intent)
                return run, node, intent
            states = {n['state'] for n in run['nodes']}
            latest = run['revisions'][-1]
            run['outputs'] = {}
            run.pop('output_error', None)
            output_error = False
            for name, ref in latest['graph']['outputs'].items():
                if ref['node_id'] is None or by_id[ref['node_id']]['state'] == 'completed':
                    binding = (dict(value=latest['inputs'][ref['port']]) if ref['node_id'] is None else
                               dict(node=ref['node_id'], port=ref['port'], channel=ref.get('channel', 'outputs')))
                    binding['pointer'] = ref.get('pointer', '')
                    if ref.get('assemble') is not None:
                        binding['assemble'] = ref['assemble']
                    try:
                        value = self._value(binding, by_id)
                        if self.interconnect:
                            self.host.validate_value({'kind': ref['kind']}, value)
                        run['outputs'][name] = value
                    except ValueError:
                        output_error = True
            if output_error:
                states.add('failed')
                run['output_error'] = 'interconnect_contract_mismatch'
            pending = states - {'completed', 'failed', 'cancelled', 'blocked'}
            run['cleanup_pending'] = [n['lab']['attempt_id'] for n in run['nodes'] if n['lab'] and
                n['lab'].get('status', {}).get('cleanup_state') not in {'reaped', 'no_container_created'}]
            run['cancellation_complete'] = run['stopping'] and not pending and not run['cleanup_pending']
            run['status'] = ('stopping' if run['stopping'] else 'waiting') if pending else (
                ('needs_reconciliation' if run['cleanup_pending'] else 'cancelled') if run['stopping']
                else 'failed' if states & {'failed', 'blocked'} else 'completed')
            self._save(db, run, 'workflow.state', status=run['status'],
                       node_states={n['id']: n['state'] for n in run['nodes']}, cleanup_pending=run['cleanup_pending'])
            return None

    def tick(self, run_id):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            run = self._get(db, run_id)
            if run['status'] == 'needs_reconciliation':
                for node in run['nodes']:
                    if node['lab'] and node['lab']['attempt_id'] in run['cleanup_pending']:
                        node['state'] = 'waiting'
                run['status'] = 'stopping'
                self._save(db, run, 'workflow.reconciliation_requested')
        claimed = self._claim(run_id)
        if claimed is None:
            return self.get(run_id)
        run, node, intent = claimed
        cap = self.capabilities[node['capability']]
        decl = self.host.describe(cap.release)['capabilities'][intent['capability']]
        # All operation calls, including status/cancel, use the host's effect
        # admission and receipts. A graph never launches a subprocess itself.
        try:
            receipt = self.host.call(cap.release, intent['capability'], intent['inputs'],
                key=intent['key'], grants=sorted(set(decl['changes']) & set(self.grants)), timeout=60)
        except Exception as error:
            # Lost acknowledgements and transport errors retain the persisted
            # intent; do not invent a terminal receipt or skip other children.
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                run = self._get(db, run_id)
                current = next(n for n in run['nodes'] if n['id'] == node['id'])
                current.update(state='unknown', error=type(error).__name__)
                self._save(db, run, 'cc.transport_error', node_id=node['id'], error=type(error).__name__)
            return run
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            run = self._get(db, run_id)
            current = next(n for n in run['nodes'] if n['id'] == node['id'])
            if current['operation'] != intent:
                return run  # Another reconciler already recorded this receipt.
            current['receipts'].append(receipt)
            current['operation'] = None
            complete = receipt['state'] == 'succeeded' and receipt['completeness'] == 'complete'
            output = receipt['outputs'].get(cap.lifecycle.get('envelope'), {}) if cap.lifecycle.get('envelope') else receipt['outputs']
            if receipt['state'] in {'running', 'unknown'}:
                # Keep the SAME intent for recovery, never spend a retry budget.
                current.update(state='unknown', operation=intent)
            elif not complete:
                current['state'] = 'waiting' if current['lab'] else 'failed'
                current['error'] = receipt.get('reason', 'incomplete_cc_result')
            elif intent['phase'] == 'call':
                current['outputs'] = receipt['outputs']
                if cap.lifecycle:
                    current['lab'] = dict(task_id=self.task_id, attempt_id=output['attempt_id'], collected=False)
                    current['state'] = 'waiting'
                else:
                    current['state'] = 'completed'
            elif intent['phase'] in {'status', 'cancel'}:
                status = output
                if status.get('task_id') != self.task_id or status.get('attempt_id') != current['lab']['attempt_id']:
                    current.update(state='waiting', error='lab_identity_mismatch')
                else:
                    current['lab']['status'] = status
                    if status['state'] in {'succeeded', 'failed', 'cancelled'}:
                        # Result collection happens even for failed/cancelled jobs.
                        current['operation'] = dict(capability=cap.lifecycle['result'],
                            inputs={'attempt_id': current['lab']['attempt_id']}, phase='result',
                            key='wf-' + digest([run_id, current['id'], 'result', current['polls']]))
            else:
                if output.get('attempt_id') != current['lab']['attempt_id']:
                    current.update(state='waiting', error='lab_result_identity_mismatch')
                    self._save(db, run, 'cc.receipt', node_id=current['id'], receipt=receipt,
                               state=current['state'], lab=current['lab'], outputs=current['outputs'])
                    return run
                current['lab'].update(result=output, collected=True)
                if self.interconnect:
                    current['completion_outputs'] = receipt['outputs']
                status = current['lab']['status']
                outcome = output.get('execution_outcome')
                if outcome in {'upload_pending', 'pending', 'running', 'unknown'}:
                    current['lab']['collected'] = False
                    current['state'] = 'waiting'
                elif (outcome in {'incomplete_evidence', 'failed', 'error'} or output.get('state') == 'failed'
                      or (output.get('analysis') or {}).get('execution_complete') is False):
                    current['state'] = 'failed'
                else:
                    current['state'] = 'completed' if status['state'] == 'succeeded' else (
                    'cancelled' if status['state'] == 'cancelled' else 'failed')
            self._save(db, run, 'cc.receipt', node_id=current['id'], receipt=receipt,
                       state=current['state'], lab=current['lab'], outputs=current['outputs'],
                       **({'completion_outputs': current.get('completion_outputs', {})} if self.interconnect else {}))
        return self.get(run_id)
