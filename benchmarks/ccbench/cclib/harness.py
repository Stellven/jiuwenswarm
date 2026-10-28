"""Run installed source workers in process; effects require explicit opt-in."""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid
from types import FunctionType

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import roots  # noqa: E402

from jiuwenswarm.research.binding import ContractFactory
from jiuwenswarm.research.checks.engine import CheckContext, CheckRegistry
from jiuwenswarm.research.checks.compiler import compiler_checks
from jiuwenswarm.research.checks.stages import ResearchChecks
from jiuwenswarm.research.checks.verifier import verifier_checks, CHECK_IDS
from jiuwenswarm.research.compiler import prepare_compiler_assets
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.gate import ProtectedGate, SemanticVerifier
from jiuwenswarm.research.planning import planner_checks
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes

ROOT = Path(__file__).resolve().parent
# Scratch stores and codex call evidence go here, never beside the source. A runner points this at its --out
# directory; the default is a temp directory (override with AI4R_BENCH_SCRATCH).
SCRATCH_ROOT = Path(os.environ.get('AI4R_BENCH_SCRATCH') or Path(tempfile.gettempdir()) / 'ccbench-scratch')
STAGES = ('intent', 'requirements', 'screening', 'evaluation', 'delivery', 'planner')


VARIANTS = {'r4fix': dict(intent_version='m1-8', screening_version='m1-6', delivery_version='m1-6')}


async def product_assets(store, variant=None):
    """Capture compose_core's opt-in releases, including its separate pilots.

    Evidence-aware review installs additional releases alongside the original
    graph selections; it does not replace evaluation/delivery globally.
    """
    options = VARIANTS[variant] if variant else {}
    from jiuwenswarm.research.capsules.assets import build_research_assets
    from jiuwenswarm.research.capsules.paper_assets import build_paper_assets
    from jiuwenswarm.research.pilot_catalog import prepare_evidence_aware_pilot_assets
    compiler = await prepare_compiler_assets(
        store, requirements_version='m1-9', intent_version=options.get('intent_version', 'm1-7'))
    research = build_research_assets(store, screening_version=options.get('screening_version', 'm1-5'),
                                     delivery_version=options.get('delivery_version', 'm1-5'))
    paper = build_paper_assets(store)
    paper.pop('paper_planner', None)
    evidence = prepare_evidence_aware_pilot_assets(
        store, compiler_assets=compiler,
        # Evidence-aware pilot variants are defined against the m1-5 releases only.
        research_assets=research if not options else build_research_assets(store), paper_assets=paper)
    return compiler, research, paper, evidence


class DirectPlanner:
    """Reconstructed NativePlanner transport; worker parsing/repair stays real.

    NativePlanner builds the installed SDK and uses system TemporaryDirectory.
    This dependency is substituted to keep offline runs in-process and confined.
    """
    async def propose(self, payload, *, invoke, instructions):
        return await invoke(json.dumps(payload, ensure_ascii=False, allow_nan=False), system=instructions)


def scratch(label='run'):
    path = Path(SCRATCH_ROOT) / (label + '-' + uuid.uuid4().hex)
    os.makedirs(path, exist_ok=False)
    return path


def transport_text(prompt, system=None):
    # Exact InvocationContext.model framing, also used for product comparison.
    return prompt if system is None else system + '\n\n<subject_payload>\n' + prompt + '\n</subject_payload>'


class ScriptedModel:
    """Replies may be strings, JSON objects or (prompt, system) callbacks."""
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    async def __call__(self, prompt, system=None):
        self.calls.append({'prompt': prompt, 'system': system})
        try:
            reply = next(self.replies)
        except StopIteration as exc:
            raise ResearchError('script_exhausted', 'No scripted reply remains') from exc
        if callable(reply):
            reply = reply(prompt, system)
        if inspect.isawaitable(reply):
            reply = await reply
        return reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False)


class CodexModel:
    """One subprocess per call, 300 seconds, no transport retries."""
    def __init__(self, model_name, *, execute=False):
        if not execute:
            raise ValueError('Codex execution requires explicit execute=True / --execute')
        self.model_name = model_name
        self.records = []

    async def __call__(self, prompt, system=None):
        directory = scratch('codex')
        outfile = directory / 'reply.txt'
        text = transport_text(prompt, system)
        (directory / 'prompt.txt').write_bytes(text.encode('utf-8'))
        argv = [roots.require_codex(), 'exec', '--skip-git-repo-check', '-m', self.model_name,
                '-s', 'read-only', '--ephemeral', '-C', str(directory), '-o', str(outfile), '-']
        record = {'argv': argv, 'directory': str(directory), 'tokens': None,
                  'token_lines': [], 'raw_reply': None}
        self.records.append(record)
        try:
            result = await asyncio.to_thread(subprocess.run, argv, input=text.encode('utf-8'),
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
                                            check=False)
        except subprocess.TimeoutExpired as exc:
            for stream in ('stdout', 'stderr'):
                raw = getattr(exc, stream, None) or b''
                (directory / (stream + '.txt')).write_bytes(raw)
            record['error'] = 'timeout'
            if outfile.exists():
                record['raw_reply'] = outfile.read_text('utf-8')
            raise ResearchError('model_timeout', 'Codex exceeded the hard 300 second timeout') from exc
        for stream in ('stdout', 'stderr'):
            (directory / (stream + '.txt')).write_bytes(getattr(result, stream))
        log = (result.stdout + b'\n' + result.stderr).decode('utf-8', errors='replace')
        record['token_lines'] = re.findall(r'(?im)^.*tokens used[^\r\n]*(?:\r?\n[\d,]+)?', log)
        counts = re.findall(r'(?im)tokens used\s*[:=]?\s*([\d,]+)', log)
        if counts:
            record['tokens'] = int(counts[-1].replace(',', ''))
        record['returncode'] = result.returncode
        if outfile.exists():
            record['raw_reply'] = outfile.read_bytes().decode('utf-8')
        if result.returncode or record['raw_reply'] is None:
            raise ResearchError('model_process_failed', f'Codex exited {result.returncode}; evidence: {directory}')
        return record['raw_reply']


class Context:
    def __init__(self, store, contract, model, prompts, calls):
        self.store, self.contract, self._model = store, contract, model
        self.prompts, self.calls = prompts, calls
        self.role = 'worker'

    def input_refs(self, port):
        matches = [p for p in self.contract['inputs'] if p['name'] == port]
        if len(matches) != 1:
            raise ResearchError('input_binding', 'Missing or duplicate input port: ' + port)
        return tuple(matches[0]['artifact_refs'])

    def input_ref(self, port):
        refs = self.input_refs(port)
        if len(refs) != 1:
            raise ResearchError('input_binding', 'Expected a single artifact: ' + port)
        return refs[0]

    def read_blob(self, ref):
        return self.store.read_blob(ref)

    def read_json(self, ref):
        return self.store.read_record(ref)

    def record_host(self, key, ref):
        from jiuwenswarm.research.binding import HOST_KEYS
        if key not in HOST_KEYS | {'planner_infeasible'}:
            raise ResearchError('host_record_invalid', 'Unknown host-record key')
        self.read_blob(ref)
        self.store.append_record('host-record-proposal', dict(
            {k: self.contract[k] for k in ('run_id', 'node_id', 'subnode_id', 'attempt_id')}, key=key, ref=ref))

    async def model(self, prompt, system=None):
        text = transport_text(prompt, system)
        self.prompts.append({'role': self.role, 'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                             'text': text, 'system': system, 'prompt': prompt})
        call = {'role': self.role, 'raw_reply': None, 'tokens': None}
        self.calls.append(call)
        try:
            call['raw_reply'] = await self._model(prompt, system=system)
            return call['raw_reply']
        except Exception as exc:
            call['error'] = getattr(exc, 'code', type(exc).__name__)
            raise
        finally:
            if isinstance(self._model, CodexModel) and self._model.records:
                call.update(self._model.records[-1])


def port(name, contract_id, refs=None, required=True):
    value = dict(name=name, contract_id=contract_id, version=ContractFactory._version(contract_id), required=required)
    if refs is not None:
        value['artifact_refs'] = refs
    return value


class Harness:
    """Persistent local store; callers can preload exact refs before run_stage."""
    def __init__(self, variant=None):
        if variant is not None and variant not in VARIANTS:
            raise ValueError('Unknown release variant: ' + str(variant))
        self.variant = variant
        self.directory = scratch()
        # Precreate with inherited Windows ACLs (store's mode=0700 is restrictive).
        for name in ('state', 'artifacts/sha256', 'inputs'):
            os.makedirs(self.directory / name, exist_ok=True)
        for n in range(256):
            os.makedirs(self.directory / 'artifacts' / 'sha256' / f'{n:02x}', exist_ok=True)
        self.store = SQLiteRunStore(self.directory)

    def close(self):
        self.store.close()

    def capture(self, value, *, record_id=None):
        raw = value if isinstance(value, bytes) else json_bytes(value)
        return self.store.put_blob(raw, record_id=record_id,
                                   media_type='application/octet-stream' if isinstance(value, bytes) else 'application/json')

    async def assets(self, stage):
        compiler, research, _, _ = await product_assets(self.store, self.variant)
        return (compiler if stage in ('intent', 'requirements', 'planner') else research)[stage]

    def contract(self, stage, asset, inputs, input_refs):
        declaration = self.store.read_record(asset['declaration_ref'])
        opaque = self.capture({'scope': 'offline cclib context; no runtime authorization'})
        refs = {name: input_refs.get(name) or self.capture(value) for name, value in inputs.items()}
        declared_names = {p['name'] for p in declaration['ports']['inputs']}
        missing = [p['name'] for p in declaration['ports']['inputs'] if p['required'] and p['name'] not in refs]
        if missing or set(refs) - declared_names:
            raise ResearchError('input_binding', 'Inputs must match declaration ports; missing: ' + repr(missing)
                                + '; unexpected: ' + repr(sorted(set(refs) - declared_names)))
        for name, ref in refs.items():
            if self.store.read_record(ref) != inputs[name]:
                raise ResearchError('input_binding', 'Supplied input ref differs from decoded value: ' + name)
        inports = [port(p['name'], p['schema_ref'], [refs[p['name']]], p['required'])
                   for p in declaration['ports']['inputs'] if p['name'] in refs]
        # compiler.IntentionCompiler._work uses its public short alias for Intent.
        if stage == 'requirements':
            next(p for p in inports if p['name'] == 'intent')['contract_id'] = 'intent-ir'
        missing = [p['name'] for p in declaration['ports']['inputs'] if p['required'] and p['name'] not in refs]
        if missing or set(refs) != {p['name'] for p in inports}:
            raise ResearchError('input_binding', 'Inputs must match declaration ports; missing: ' + repr(missing))
        outputs = [port(p['name'], p['schema_ref'], required=p['required']) for p in declaration['ports']['outputs']]
        limits = {'time_s': 300, 'model_calls': 2 if stage == 'planner' else 1, 'memory_mb': 256}
        implementations = list(asset.get('implementation_refs') or asset['body_refs'].values())
        return dict(schema_version='1.0.0', id='cclib.' + stage, run_id='cclib', node_id=stage,
                    subnode_id=stage, attempt_id='a1', revision=1, objective='Offline ' + stage,
                    requirement_ids=['offline_stage'], inputs=inports, outputs=outputs, input_refs=list(refs.values()),
                    required_outputs=[p['name'] for p in outputs], evidence_obligations=['offline_capture'],
                    subnode_limits=limits, checking_profile_ref=asset['profile_ref'], policy_ref=opaque,
                    configuration_ref=opaque, template_ref=opaque, node_contract_ref=opaque,
                    bindings=[dict(id='work', role='work', declaration_ref=asset['declaration_ref'],
                        implementation_refs=implementations, dependency_refs=[], admission_ref=opaque, limits=limits,
                        effective_authority=dict(network='none', network_allowlist=[], resource_reads=list(refs.values()),
                                                 write_roots=[], tools=[]))])

    def plan(self, contract_ref, contract, asset, ids):
        profile = self.store.read_record(asset['profile_ref'])
        value = dict(schema_version='2.0.0', id='plan:' + uuid.uuid4().hex, contract_ref=contract_ref,
                     input_refs=contract['input_refs'], profile_ref=asset['profile_ref'], policy_ref=contract['policy_ref'],
                     mandatory_deterministic=ids, mandatory_semantic=[c['criterion_id'] for c in profile['criteria'] if c['blocking']],
                     runner_refs=[asset['runner_ref']], node_contract_ref=contract['node_contract_ref'], subnode_id=contract['subnode_id'])
        return value, self.store.put_record('bound-check-plan', value)

    async def run_stage(self, stage, inputs, model_name='gpt-6.1-sol', *, model=None, execute=False, input_refs=None):
        if stage not in STAGES:
            raise ValueError('Unknown stage: ' + stage)
        # Reject implicit effects before even constructing assets.
        model = model if model is not None else CodexModel(model_name, execute=execute)
        prompts, calls, outputs, output_refs, results, findings, decisions = [], [], {}, {}, [], [], []
        failure = None
        contract = None
        try:
            asset = await self.assets(stage)
            label = self.store.read_record(asset['declaration_ref'])['identity']['version_label']
            if stage == 'screening' and label != 'm1-6':
                from jiuwenswarm.research.contracts import contract_schema
                limit = contract_schema('screening-result')['properties']['scores'].get('maxItems')
                count = len(inputs.get('candidate_set', {}).get('ideas', []))
                if limit is not None and count > limit:
                    raise ResearchError('capability_mismatch',
                        f'Pinned screening-result permits at most {limit} scores; '
                        f'candidate_set supplies {count} ideas. Cannot preserve every identity; '
                        'a compatible admitted release is required.')
            contract = self.contract(stage, asset, inputs, input_refs or {})
            cref = self.store.put_record('subnode-execution-contract', contract)
            bundle = self.store.read_record(asset['bundle_ref'])
            ids = [c['check_id'] for c in bundle['checks']]
            mandatory = [c['check_id'] for c in bundle['checks'] if c['blocking']]
            plan, pref = self.plan(cref, contract, asset, mandatory)
            ctx = Context(self.store, contract, model, prompts, calls)
            from jiuwenswarm.research.capsules import intent, requirements_m1_9, screening, evaluation, delivery, planner
            handler = {'intent': intent.execute, 'requirements': requirements_m1_9.execute,
                       'evaluation': evaluation.execute, 'delivery': delivery.execute, 'planner': planner.execute}.get(stage)
            if stage == 'planner':
                # Copy globals instead of monkeypatching a shared module; safe for
                # independent concurrent harness instances, exact worker bytecode.
                handler = FunctionType(planner.execute.__code__, dict(planner.execute.__globals__, NativePlanner=DirectPlanner))
            if stage == 'intent' and label == 'm1-8':
                from jiuwenswarm.research.capsules import intent_m1_8
                handler = intent_m1_8.execute
            if stage == 'delivery' and label == 'm1-6':
                from jiuwenswarm.research.capsules import delivery_evidence
                handler = delivery_evidence.execute
            if stage == 'screening' and label == 'm1-6':
                from jiuwenswarm.research.capsules import screening_weighted
                from jiuwenswarm.research.capsules.ranking_weighted import rank_weighted
                handler = screening_weighted.WeightedScreeningCarrier(rank_weighted, asset['body_refs']['ranking_weighted.py'],
                                                                      asset['body_refs']['screening_weighted_prompt.txt']).execute
            elif stage == 'screening':
                from jiuwenswarm.research.capsules.ranking import rank_opportunities
                handler = screening.ScreeningCarrier(rank_opportunities, asset['body_refs']['ranking_parent.txt'],
                                                      asset['body_refs']['screening_prompt.txt']).execute
            try:
                produced = await handler(ctx, inputs)
            except ResearchError as exc:
                if exc.code not in {'invalid_output', 'contract_invalid'}:
                    raise
                # As CapsuleRunner._run does on a rejected worker return: there
                # are no output artifacts to check or review. Do not claim the
                # independent source bundle was evaluated.
                rawref = self.capture(calls[-1]['raw_reply'].encode('utf-8'))
                results = [dict(check_id=key, outcome='FAIL',
                                reason='Worker deterministic validation rejected before check bundle: ' + str(exc),
                                evidence_refs=[rawref]) for key in mandatory]
                dref = self.store.put_record('deterministic-check-result', dict(schema_version='1.0.0',
                    subject_ref=rawref, check_plan_ref=pref, results=results))
                gate = ProtectedGate(self.store).decide(cref, pref, dref, None, [], [rawref], halt_reason=exc.code)
                decisions.append(self.store.read_record(gate))
                raise
            for name, item in produced.items():
                raw = item.data
                output_refs[name] = self.store.put_blob(raw, media_type=item.media_type)
                outputs[name] = json.loads(raw) if item.media_type == 'application/json' else raw
            observation = {'outcome': 'success', 'observed_runtime': True,
                           'basis': 'in-process Python return; no installed runtime observation'}
            oref = self.capture(observation)
            checkctx = CheckContext(contract, self.store, inputs, outputs, output_refs, observation)
            if stage == 'screening' and label == 'm1-6':
                from jiuwenswarm.research.checks.screening_weighted import WeightedScreeningChecks
                checks = WeightedScreeningChecks(stage)
            elif stage == 'delivery' and label == 'm1-6':
                from jiuwenswarm.research.checks.delivery_evidence import DeliveryEvidenceChecks
                checks = DeliveryEvidenceChecks(stage)
            else:
                checks = compiler_checks if stage in ('intent', 'requirements') else planner_checks if stage == 'planner' else ResearchChecks(stage)
            registry = CheckRegistry()
            registry.register_bundle(bundle['bundle_id'], ids, checks,
                                     implementation_ref=asset['runner_ref'], profile_ref=asset['profile_ref'])
            results = await registry.run(plan, checkctx, bundle_id=bundle['bundle_id'])
            dref = self.store.put_record('deterministic-check-result', dict(schema_version='1.0.0',
                subject_ref=next(iter(output_refs.values())), subject_refs=list(output_refs.values()), check_plan_ref=pref, results=results))
            if any(r['outcome'] != 'PASS' for r in results if r['check_id'] in mandatory):
                failure = 'deterministic_check_failed'
            if any(isinstance(v, dict) and (v.get('readiness', {}).get('status') == 'needs_clarification'
                   or any(x.get('blocking') for x in v.get('uncertainties', []))
                   or any(x.get('blocking') for x in v.get('unresolved_items', []))) for v in outputs.values()):
                failure = failure or 'blocking_uncertainty'
            if failure:
                gate = ProtectedGate(self.store).decide(cref, pref, dref, None, list(output_refs.values()), [oref], halt_reason=failure)
                decisions.append(self.store.read_record(gate))
            else:
                for name, ref in output_refs.items():
                    profile = self.store.read_record(asset['profile_ref'])
                    criteria_ids = [c['criterion_id'] for c in profile['criteria'] if c['target_port'] in (None, name)]
                    review = dict(schema_version='2.0.0', id='review:' + uuid.uuid4().hex,
                        subject_ref=ref, contract_ref=cref, check_plan_ref=pref, input_refs=contract['input_refs'],
                        deterministic_result_ref=dref, criteria=criteria_ids, observations=[oref],
                        evidence_classes=['offline_in_process'], node_contract_ref=contract['node_contract_ref'], subnode_id=stage)
                    rref = self.store.put_record('review-context', review)
                    ctx.role = 'verifier:' + name
                    aref = await SemanticVerifier(self.store).review(asset['declaration_ref'], ref, asset['profile_ref'], rref, name, ctx.model)
                    assessment = self.store.read_record(aref)
                    findings.append(dict(port=name, **assessment))
                    vc = copy.deepcopy(contract)
                    vc.update(id='cclib.verifier.' + name, subnode_id=stage + '.verifier',
                              inputs=[port('subject_declaration', 'capsule-declaration', [asset['declaration_ref']]),
                                      port('subject_output', 'opaque-bytes', [ref])])
                    vc['input_refs'] = [asset['declaration_ref'], ref]
                    vc['bindings'][0]['role'] = 'verifier'
                    vcref = self.store.put_record('subnode-execution-contract', vc)
                    vp, vpref = self.plan(vcref, vc, asset, list(CHECK_IDS))
                    vctx = CheckContext(vc, self.store, {}, {'verifier_assessment': assessment}, {'verifier_assessment': aref}, observation)
                    mechanical = verifier_checks(vctx, {}, vctx.outputs)
                    vref = self.store.put_record('deterministic-check-result', dict(schema_version='1.0.0',
                        subject_ref=aref, check_plan_ref=vpref, results=mechanical))
                    gate = ProtectedGate(self.store).decide(cref, pref, dref, aref, [ref], [oref],
                                                           output_port=name, verifier_check_ref=vref)
                    decisions.append(self.store.read_record(gate))
        except Exception as exc:
            failure = str(getattr(exc, 'code', type(exc).__name__)) + ': ' + str(exc)
        reasons = [r['check_id'] + ': ' + r['reason'] for r in results if r['outcome'] != 'PASS']
        reasons += [r['message'] for d in decisions if d['action'] == 'halt' for r in d['reasons']]
        if failure:
            reasons.append(failure)
        advanced = bool(decisions) and not failure and all(d['action'] == 'advance' for d in decisions)
        if advanced:
            reasons = ['All mandatory checks and semantic criteria passed']
        counts = [c['tokens'] for c in calls]
        public_outputs = {k: v.decode('utf-8') if isinstance(v, bytes) else v for k, v in outputs.items()}
        return dict(status='advance' if advanced else 'halt', output=public_outputs, output_refs=output_refs,
                    check_results=results, verifier_findings=findings, prompts=prompts, model_calls=len(calls),
                    calls=calls, tokens=sum(counts) if counts and all(n is not None for n in counts) else None,
                    reasons=reasons, gate_decisions=decisions, scratch=str(self.directory),
                    label='offline CC logic, prompts reconstructed')


def run_stage(stage, inputs, model_name='gpt-6.1-sol', *, model=None, execute=False):
    """Synchronous convenience; use Harness.run_stage in an existing event loop."""
    harness = Harness()
    try:
        return asyncio.run(harness.run_stage(stage, inputs, model_name, model=model, execute=execute))
    finally:
        harness.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=STAGES)
    parser.add_argument('inputs', type=Path, help='JSON: inputs, optional blobs [{ref,text|base64}], input_refs')
    parser.add_argument('--model', default='gpt-6.1-sol')
    parser.add_argument('--out', type=Path, required=True, help='directory for scratch stores and codex call evidence')
    parser.add_argument('--execute', action='store_true', help='Authorize Codex subprocess/model calls (never implicit)')
    args = parser.parse_args()
    if not args.execute:
        parser.error('Live calls require --execute; use ScriptedModel through the Python API for offline tests')
    import base64
    global SCRATCH_ROOT
    SCRATCH_ROOT = args.out / '.scratch'
    value = json.loads(args.inputs.read_text('utf-8'))
    h = Harness()
    try:
        for blob in value.get('blobs', []):
            raw = base64.b64decode(blob['base64']) if 'base64' in blob else blob['text'].encode('utf-8')
            ref = h.capture(raw, record_id=blob['ref']['id'])
            if ref != blob['ref']:
                raise ValueError('Blob hash differs from supplied ref')
        result = asyncio.run(h.run_stage(args.stage, value['inputs'], args.model, execute=True, input_refs=value.get('input_refs')))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        h.close()


if __name__ == '__main__':
    main()
