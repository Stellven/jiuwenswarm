"""invoke and admit: the portable guarantees around one capability capsule.

Guarantee order for ``invoke``: pins, admission, input guard, worker (time
limited), output port conformance, the capsule's own checks. Outputs are
returned only when every stage passed. Every error code from the capsule or the
contract layer passes through as the halt code.
"""
from __future__ import annotations

import asyncio
import copy
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace

from jiuwenswarm.research.capsule_extensions.packet import PACKET, validate_packet
from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.state import json_bytes

from . import semantic
from .modelgate import ModelGate, call_limit
from .loader import Capsule, discover, sha256, verify_pins

RECEIPT_VERSION = 'capsule-runtime-receipt:1'


def now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def run_sync(coro):
    """Run a coroutine from sync code, even when a loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coro).result()


class Halt(Exception):
    def __init__(self, stage: str, code: str, reason: str):
        super().__init__(stage + ':' + code)
        self.stage, self.code, self.reason = stage, code, reason


def _from_error(stage: str, error: Exception) -> Halt:
    if isinstance(error, ResearchError):
        return Halt(stage, error.code, error.message)
    return Halt(stage, 'unexpected_' + type(error).__name__, str(error)[:300])


def _validate_port(port: dict, value) -> None:
    """Schema check for one port value; packet ports also get validate_packet."""
    validate(port['schema_ref'], value)
    if port['schema_ref'] == PACKET:
        validate_packet(value)


def guard_inputs(declaration: dict, inputs, ports=None, stage=None) -> None:
    ports = ports if ports is not None else declaration['ports']['inputs']
    if not isinstance(inputs, dict):
        raise Halt('input_guard', 'inputs_type', 'Inputs must be an object keyed by input port name')
    names = {p['name'] for p in ports}
    unknown = sorted(set(inputs) - names)
    if unknown:
        raise Halt('input_guard', 'unknown_input', 'Undeclared input port(s): ' + ', '.join(unknown))
    for port in ports:
        if port['name'] not in inputs:
            if port['required']:
                raise Halt('input_guard', 'missing_input', 'Required input port missing: ' + port['name'])
            continue
        try:
            if stage is not None:
                stage.validate_port(port['name'], inputs[port['name']])
            else:
                _validate_port(port, inputs[port['name']])
        except ResearchError as error:
            raise Halt('input_guard', error.code, port['name'] + ': ' + error.message) from error


def _canonical(artifact) -> tuple[bytes, object]:
    """Bytes and decoded JSON value of one produced artifact."""
    data = getattr(artifact, 'data', artifact)
    if isinstance(data, (bytes, bytearray)):
        raw = bytes(data)
    elif isinstance(data, str):
        raw = data.encode('utf-8')
    else:
        raw = json_bytes(data)
    try:
        return raw, json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeError) as error:
        raise ResearchError('output_not_json', 'Produced artifact is not JSON') from error


def _contract_for(capsule: Capsule, caller: dict | None) -> dict:
    declaration = capsule.declaration
    base = {'capability_id': capsule.capability_id, 'version': capsule.version, 'node_id': capsule.capability_id,
            'attempt_id': 'portable-' + uuid.uuid4().hex[:12], 'requirement_ids': [],
            'policy_ref': {'id': 'portable-policy', 'sha256': '0' * 64},
            'node_contract_ref': {'id': 'portable-contract', 'sha256': sha256(json_bytes(declaration))},
            'limits': {'wall_s': capsule.wall_s, **declaration['budget']['per_call']},
            'effects': declaration['changes']['effects'], 'effect_class': declaration['changes']['effect_class']}
    base.update(caller or {})
    return base


async def _run_worker(capsule: Capsule, ctx, inputs, wall_s: float):
    if ctx.model is not None:
        # A caller model client may be bound to this event loop, so stay on it.
        # The time limit then holds for any worker that awaits; see README risks.
        return await asyncio.wait_for(capsule.execute(ctx, inputs), wall_s)
    # Pure workers are plain CPU code behind an async signature. Run in a daemon
    # thread so the time limit still fires; a runaway thread is abandoned.
    loop = asyncio.get_running_loop()
    done = loop.create_future()

    def settle(setter, value):
        if not done.done():
            setter(value)

    def target():
        try:
            outcome = (done.set_result, asyncio.run(capsule.execute(ctx, inputs)))
        except BaseException as error:  # reported to the caller, never swallowed
            outcome = (done.set_exception, error)
        try:
            loop.call_soon_threadsafe(settle, *outcome)
        except RuntimeError:
            pass  # the caller timed out and its loop is gone; the abandoned result is dropped

    threading.Thread(target=target, daemon=True, name='capsule-' + capsule.capability_id).start()
    return await asyncio.wait_for(done, wall_s)


def stage_lines(capsule: Capsule) -> list[str]:
    plan = semantic.verifier_plan(capsule)
    return ['deterministic checks (checks.py): ' + ', '.join(plan['deterministic_checks']),
            'trace: ' + ('applies' if plan['trace'] else 'not_applicable (' + plan['trace_why'] + ')'),
            'semantic verifier: ' + ('applies (' if plan['semantic'] else 'not_applicable (') + plan['semantic_why'] + ')']


class Runtime:
    """One process-local view: loaded capsules plus what has been admitted."""

    aliases: dict = {}

    def __init__(self, extra_dirs=(), *, include_builtin: bool = True, worker_model=None, include_stages: bool | None = None):
        """worker_model: server-configured default backend for ctx.model (callable(prompt, system=None) -> text)."""
        self.worker_model = worker_model
        self.extra_dirs = tuple(extra_dirs)
        self.capsules: dict[str, Capsule] = discover(self.extra_dirs, include_builtin=include_builtin)
        self.admitted: dict[str, dict] = {}
        if include_stages if include_stages is not None else include_builtin:
            from .stage_adapter import ALIASES, load_stage_capsules
            self.capsules.update(load_stage_capsules())
            self.aliases = dict(ALIASES)

    # --- lookup -------------------------------------------------------
    def get(self, capability_id: str) -> Capsule:
        capsule = self.capsules.get(self.aliases.get(capability_id, capability_id))
        if capsule is None:
            raise KeyError('Unknown capability: ' + capability_id)
        return capsule

    def list(self) -> list[dict]:
        return [{'id': key, 'capability_id': c.capability_id, 'version': c.version, 'status': c.status,
                 'admitted': key in self.admitted, 'reason': c.reason, 'release_hash': c.release_hash,
                 'summary': c.declaration.get('identity', {}).get('summary', '')}
                for key, c in self.capsules.items()]

    def describe(self, capability_id: str) -> dict:
        c = self.get(capability_id)
        d = c.declaration
        info = {'id': c.key, 'capability_id': c.capability_id, 'version': c.version, 'status': c.status,
                'reason': c.reason, 'refusal_code': c.refusal_code, 'admitted': c.key in self.admitted,
                'release_hash': c.release_hash, 'module': c.module}
        if d:
            info.update(summary=d['identity']['summary'], kind=d['identity']['kind'],
                        ports={**d['ports'], 'inputs': c.ports_in()}, limits=d['budget']['per_call'],
                        effect_class=d['changes']['effect_class'], effects=d['changes']['effects'],
                        needs_model=bool(d['needs']['injects']), network=d['needs']['network']['mode'],
                        checks=[x['id'] for x in d['guarantees']['checks']],
                        acceptance=d['guarantees']['acceptance'], unanchored=d['guarantees']['unanchored'],
                        pinned_files=c.release.get('files', {}), verifier_stages=stage_lines(c))
        return info

    # --- admission ----------------------------------------------------
    def admit(self, capability_id: str, *, model=None, contract=None, cases=None) -> dict:
        from .admission import admit_capsule
        capsule = self.get(capability_id)
        result = run_sync(admit_capsule(self, capsule, model=model, contract=contract, cases=cases))
        if result['passed']:
            self.admitted[capsule.key] = result
        else:
            self.admitted.pop(capsule.key, None)
        return result

    # --- invoke -------------------------------------------------------
    def invoke(self, capability_id: str, inputs, *, model=None, contract=None, require_admission: bool = True,
               verifier_model=None, require_semantic: bool = False, worker_model=None) -> dict:
        return run_sync(self.ainvoke(capability_id, inputs, model=model, worker_model=worker_model, contract=contract,
                                     require_admission=require_admission, verifier_model=verifier_model,
                                     require_semantic=require_semantic))

    async def ainvoke(self, capability_id: str, inputs, *, model=None, contract=None,
                      require_admission: bool = True, verifier_model=None, require_semantic: bool = False,
                      worker_model=None, _mutate_outputs=None, _admitting: bool = False) -> dict:
        """worker_model (alias: model): async callable(prompt, system=None) -> text that backs ctx.model.
        verifier_model: callable(prompt) -> text (sync or async), used only by capsules whose
        declaration carries semantic review. require_semantic halts when such a capsule has no model."""
        started = now()
        capability_id = self.aliases.get(capability_id, capability_id)
        capsule = self.capsules.get(capability_id)
        if capsule is None:
            return self._halted(None, capability_id, started, Halt('input_guard', 'unknown_capability',
                                'No capability with id ' + repr(capability_id)), {})
        ledger: dict = {}
        try:
            await self._pins(capsule, require_admission, ledger)
            plan = semantic.verifier_plan(capsule)
            ledger['plan'] = plan
            require_semantic = require_semantic or (capsule.semantic_required and not _admitting)
            if require_semantic and verifier_model is None:
                raise Halt('semantic_verifier', 'no_model', 'require_semantic=True but no verifier model is configured')
            guard_inputs(capsule.declaration, inputs, capsule.input_ports, capsule.stage)
            ledger['input_sha256'] = sha256(json_bytes(inputs))
            outputs, produced = await self._work(capsule, inputs, worker_model or model or self.worker_model, contract, ledger)
            if _mutate_outputs is not None:  # admission only: prove the verifier rejects altered outputs
                outputs = _mutate_outputs(outputs)
            self._verify(capsule, inputs, outputs, ledger)
            await self._deeper(capsule, outputs, ledger, verifier_model)
        except Halt as halt:
            return self._halted(capsule, capability_id, started, halt, ledger)
        receipt = self._receipt(capsule, started, 'delivered', ledger, None)
        return {'status': 'delivered', 'outputs': outputs, 'receipt': receipt}

    async def _pins(self, capsule: Capsule, require_admission: bool, ledger: dict) -> None:
        if capsule.status != 'loaded':
            raise Halt('pin', capsule.refusal_code or 'refused', capsule.reason or 'Capsule refused at load')
        try:
            if capsule.stage:
                release_hash = capsule.stage.verify_pins()
            else:
                _, release_hash = verify_pins(capsule.root, capsule.module)
        except ResearchError as error:
            raise Halt('pin', error.code, error.message) from error
        if release_hash != capsule.release_hash:
            raise Halt('pin', 'extension_manifest', 'release.json changed since load')
        if require_admission and capsule.key not in self.admitted:
            raise Halt('pin', 'not_admitted', 'Capsule has not passed admission in this process; call admit() first '
                       'or pass require_admission=False explicitly')

    async def _work(self, capsule: Capsule, inputs: dict, model, contract, ledger: dict):
        declaration = capsule.declaration
        needs_model = bool(declaration['needs']['injects'])
        if needs_model and model is None:
            raise Halt('worker', 'no_model', 'This capsule needs a model for ctx.model and none is available: pass worker_model=, '
                       'start the server with --worker-cmd or --worker-openai-base-url/--worker-model, or use an MCP client '
                       'that supports sampling')
        merged = _contract_for(capsule, contract)
        if needs_model and not capsule.stage and not (contract or {}).get('objective'):
            raise Halt('worker', 'contract_required', 'This capsule needs a task contract with an objective')
        contract_ref = {'id': 'contract:' + sha256(json_bytes(merged))[:24], 'sha256': sha256(json_bytes(merged))}
        ledger['contract'], ledger['contract_ref'] = merged, contract_ref
        # output_refs are computed from output hashes after the worker; the worker
        # sees an empty mapping, which is what a worker sees before it has produced.
        gate = ModelGate(model, call_limit(declaration)) if needs_model else None
        ledger['worker_gate'] = gate
        native = inputs
        if capsule.stage:
            ctx, native, call = capsule.stage.bind(inputs, gate, merged)
            ledger['stage_call'], ledger['native_inputs'] = call, native
        else:
            ctx = SimpleNamespace(output_refs={}, model=gate, contract=merged, limits=merged['limits'],
                                  contract_ref=contract_ref, observation={'contract_ref': contract_ref},
                                  capability_id=capsule.capability_id)
        try:
            produced = await _run_worker(capsule, ctx, copy.deepcopy(native), capsule.wall_s)
        except asyncio.TimeoutError:
            raise Halt('worker', 'timeout', 'Worker exceeded the declared wall time of %ss' % capsule.wall_s) from None
        except Halt:
            raise
        except Exception as error:
            raise _from_error('worker', error) from error
        ports = {p['name']: p for p in declaration['ports']['outputs']}
        if not isinstance(produced, dict):
            raise Halt('worker', 'output_ports', 'Worker must return an object keyed by output port name')
        extra = sorted(set(produced) - set(ports))
        missing = sorted(n for n, p in ports.items() if p['required'] and n not in produced)
        if extra or missing:
            raise Halt('worker', 'output_ports', 'Output ports differ from the declaration (extra %s, missing %s)' % (extra, missing))
        outputs, hashes, raws = {}, {}, {}
        for name, artifact in produced.items():
            try:
                raw, value = _canonical(artifact)
                _validate_port(ports[name], value)
            except ResearchError as error:
                raise Halt('worker', error.code, name + ': ' + error.message) from error
            outputs[name], hashes[name], raws[name] = value, sha256(raw), raw
        ledger['output_sha256'], ledger['raws'] = hashes, raws
        return outputs, produced

    def _verify(self, capsule: Capsule, inputs: dict, outputs: dict, ledger: dict) -> None:
        ctx = SimpleNamespace(output_refs={n: {'id': 'output:' + n + ':' + h[:16], 'sha256': h}
                                           for n, h in ledger['output_sha256'].items()},
                              model=None, contract=ledger.get('contract'),
                              contract_ref=ledger.get('contract_ref'),
                              observation={'contract_ref': ledger.get('contract_ref')})
        ledger['check_verdict'] = 'FAIL'
        if capsule.stage:
            ctx = capsule.stage.verify_ctx(ledger['stage_call'], ctx.output_refs)
            inputs = ledger['native_inputs']
            ledger['not_applicable'] = capsule.stage.NOT_APPLICABLE
        try:
            rows = capsule.check(ctx, copy.deepcopy(inputs), copy.deepcopy(outputs))
        except Exception as error:
            ledger['checks'] = []
            raise _from_error('verifier', error) from error
        ledger['checks'] = [{'check_id': r.get('check_id'), 'outcome': r.get('outcome'), 'reason': r.get('reason')}
                            for r in rows]
        failed = [r for r in ledger['checks'] if r['outcome'] != 'PASS']
        required = set(capsule.declaration['guarantees']['acceptance'])
        absent = sorted(required - {r['check_id'] for r in ledger['checks']})
        if failed:
            raise Halt('verifier', 'check_failed', '; '.join('%s: %s' % (r['check_id'], r['reason']) for r in failed))
        if absent:
            raise Halt('verifier', 'check_missing', 'Declared acceptance checks did not run: ' + ', '.join(absent))
        ledger['check_verdict'] = 'PASS'
        ledger.setdefault('verifiers', {})['deterministic'] = 'pass'

    async def _deeper(self, capsule: Capsule, outputs: dict, ledger: dict, verifier_model) -> None:
        """Trace, packet review, then the semantic verifier, in that order; each only when it applies."""
        plan = ledger['plan']
        stages = ledger.setdefault('verifiers', {'deterministic': 'pass'})
        trace = semantic.run_trace(outputs)
        if trace is None:
            stages['trace'] = 'not_applicable (' + plan['trace_why'] + ')'
        else:
            ledger['trace'] = {'blocking_failures': trace['blocking_failures'], 'advance': trace['advance']}
            if trace['blocking_failures']:
                stages['trace'] = 'fail'
                raise Halt('trace', 'trace_failed', 'Trace predicate(s) failed: ' + ', '.join(trace['blocking_failures']))
            stages['trace'] = 'pass' if trace['advance'] else 'pass (some predicates not assessable)'
        review = semantic.run_packet_review(capsule, outputs)
        if review is None:
            stages['packet_review'] = 'not_applicable (output is not a science review packet)'
        else:
            ledger['packet_review'] = {k: {'advance': v['advance'], 'blocking_failures': v['blocking_failures']} for k, v in review.items()}
            failed = sorted(f for v in review.values() for f in v['blocking_failures'])
            if failed:
                stages['packet_review'] = 'fail'
                raise Halt('trace', 'packet_review_failed', 'Packet review failed: ' + ', '.join(failed))
            stages['packet_review'] = 'pass'
        if not plan['semantic']:
            stages['semantic'] = 'not_applicable (' + plan['semantic_why'] + ')'
            return
        if verifier_model is None:
            stages['semantic'] = 'not_run (no model configured)'
            ledger['semantic'] = {'status': 'not_run', 'reason': 'no model configured'}
            return
        vgate = ModelGate(verifier_model, len(ledger['raws']), single_arg=True)
        ledger['verifier_gate'] = vgate
        try:
            reviews = await semantic.run_semantic(capsule, outputs, ledger['raws'], vgate)
        except Exception as error:
            stages['semantic'] = 'fail'
            ledger['semantic'] = {'status': 'error', 'calls': vgate.calls}
            raise _from_error('semantic_verifier', error) from error
        ledger['semantic'] = {'status': 'reviewed', 'reviews': reviews, 'calls': vgate.calls}
        refusal = semantic.judge(reviews)
        if refusal:
            stages['semantic'] = 'fail'
            raise Halt('semantic_verifier', refusal[0], refusal[1])
        stages['semantic'] = 'pass'

    @staticmethod
    def _independent(ledger: dict):
        """None when the two models were not both used; else whether they are different backends."""
        worker, verifier = ledger.get('worker_gate'), ledger.get('verifier_gate')
        if worker is None or verifier is None:
            return None
        return worker.meta['identity'] != verifier.meta['identity']

    def _receipt(self, capsule: Capsule | None, started: str, status: str, ledger: dict, halt: dict | None) -> dict:
        receipt = {'schema': RECEIPT_VERSION, 'status': status,
                   'capability_id': capsule.capability_id if capsule else None,
                   'version': capsule.version if capsule else None,
                   'release_hash': capsule.release_hash if capsule else None,
                   'declaration_sha256': sha256(json_bytes(capsule.declaration)) if capsule and capsule.declaration else None,
                   'input_sha256': ledger.get('input_sha256'), 'output_sha256': ledger.get('output_sha256', {}),
                   'check_verdict': ledger.get('check_verdict', 'NOT_RUN'), 'checks': ledger.get('checks', []),
                   'declared_effects': {'effect_class': capsule.declaration['changes']['effect_class'],
                                        'effects': capsule.declaration['changes']['effects']}
                   if capsule and capsule.declaration else None,
                   'verifiers': ledger.get('verifiers', {}),
                   **({'not_applicable_outside_pipeline': ledger['not_applicable']} if ledger.get('not_applicable') else {}),
                   'worker_model': ledger['worker_gate'].summary() if ledger.get('worker_gate') else None,
                   'model_calls': ledger['worker_gate'].calls if ledger.get('worker_gate') else [],
                   'verifier_independent': self._independent(ledger),
                   'semantic_verifier': ledger.get('semantic') or {'status': 'not_run', 'reason': 'not reached'},
                   'trace': ledger.get('trace'), 'packet_review': ledger.get('packet_review'),
                   'admitted': bool(capsule and capsule.key in self.admitted),
                   'started_at': started, 'finished_at': now(), 'halt': halt}
        receipt['receipt_sha256'] = sha256(json_bytes(receipt))
        return receipt

    def _halted(self, capsule, capability_id, started, halt: Halt, ledger: dict) -> dict:
        info = {'stage': halt.stage, 'code': halt.code, 'reason': halt.reason}
        return {'status': 'halted', 'halt': info, 'receipt': self._receipt(capsule, started, 'halted', ledger, info)}
