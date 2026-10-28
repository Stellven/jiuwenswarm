"""In-process admission: evidence that a capsule's guards and verifier bite.

The protected admission executor (research/admission_executor.py) needs a run
store, a root broker and a Linux kernel sandbox, so it cannot run here. None of
the shipped declarations list ``self_tests`` either. This module runs a smaller,
honest substitute and reports exactly what it ran:

1. pins and declaration load cleanly (already true if the capsule is loaded);
2. no declared self-test is left unrun (a capsule that declares protected
   self-tests is not admitted here, because they cannot run here);
3. positive cases deliver through the full invoke path;
4. generic negative cases (missing port, malformed value) halt at input_guard,
   and capsule-specific negative cases halt where expected;
5. the verifier rejects a tampered copy of each delivered output.

Admission is process-local and is not the AI4R library admission.
"""
from __future__ import annotations

import copy
import hashlib
import json

from .engine import Runtime
from .loader import Capsule


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _packet(data, files=(), limitations=('Synthetic admission input, not a research conclusion',)):
    return {'schema_version': '1.0.0', 'data': data,
            'files': [{'path': p, 'text': t, 'sha256': _digest(t)} for p, t in files],
            'trust': 'low', 'provenance': [], 'limitations': list(limitations)}


def _calc(operations=('count', 'sum', 'mean', 'min', 'max')):
    return _packet({'table': {'columns': ['v'], 'rows': [[1], [2], [3]]},
                    'calculation': {'columns': ['v'], 'operations': list(operations), 'numeric_mode': 'json_numbers'}})


def _table(text='name,value\r\n"a,b",002\r\n'):
    return _packet({'table_request': {'file': 'input', 'format': 'csv', 'columns': ['name', 'value'], 'delimiter': ','}},
                   files=[('input', text)])


def _report(path='report.md'):
    return _packet({'answer': {'count': 2}, 'report': {'path': path, 'title': 'Results',
                    'sections': [{'heading': 'Summary', 'text': 'Supplied claims only.'}], 'data_keys': ['answer']}})


def _summary():
    ref = lambda name: {'id': name, 'sha256': _digest(name)}
    sections = {name: {'status': 'supported' if name == 'results' else 'not_stated',
                       'text': 'A bounded source statement.', 'citation_ids': ['C1'] if name == 'results' else []}
                for name in ('problem', 'method', 'results', 'contributions', 'limitations')}
    return {'schema_version': '1.0.0', 'id': 'paper_summary', 'brief_ref': ref('brief'), 'documents_ref': ref('documents'),
            'title': 'Example study', 'documents': [{'document_id': 'P1', 'source_ref': ref('pdf'), 'page_count': 1}],
            'sections': sections, 'citations': [{'citation_id': 'C1', 'document_id': 'P1', 'page': 1,
                                                 'start': 0, 'end': 8, 'quote': 'Evidence.'}]}


def _bad_calc():
    packet = _calc()
    packet['data']['calculation']['columns'] = ['no_such_column']
    return packet


# Keyed by capsule folder name. positive: must deliver. worker_halts: must halt
# at stage 'worker' (the capsule refuses a well-formed but semantically bad input).
BUILTIN_CASES = {
    'calculate_typed': {'positive': [_calc()], 'worker_halts': [_bad_calc()]},
    'calculate_v4': {'positive': [_calc()], 'worker_halts': [_bad_calc()]},
    'table_normalize_typed': {'positive': [_table()], 'worker_halts': [_table('wrong,header\r\na,1\r\n')]},
    'table_normalize_v3': {'positive': [_table()], 'worker_halts': [_table('wrong,header\r\na,1\r\n')]},
    'markdown_report_typed': {'positive': [_report()], 'worker_halts': [_report('../escape.md')]},
    'markdown_report_v2': {'positive': [_report()], 'worker_halts': [_report('../escape.md')]},
    'packet_report': {'positive': [_report()], 'worker_halts': [_report('../escape.md')]},
    'generalist_v2': {'positive': [_packet({'question': 'portable admission'})], 'worker_halts': [],
                      'model_reply': '{"data":{},"files":[],"expression":null,"limitations":[]}'},
    'summary_to_packet': {'positive': [None], 'worker_halts': []},   # None -> summary input, see below
}


def cases_for(capsule: Capsule, override=None):
    if override is not None:
        return override
    if capsule.stage:
        return capsule.stage.admission_cases()
    found = BUILTIN_CASES.get(capsule.module)
    if found is None:
        return None
    port = capsule.declaration['ports']['inputs'][0]['name']
    wrap = lambda value: {port: _summary() if value is None else value}
    return {'positive': [wrap(v) for v in found['positive']], 'worker_halts': [wrap(v) for v in found['worker_halts']],
            'model_reply': found.get('model_reply')}


def _tamper(value):
    """A copy of a packet output that no honest recomputation can reproduce."""
    changed = copy.deepcopy(value)
    changed['data'] = dict(changed['data'], tampered_by_admission=1)
    return changed


def _flip_trust(value):
    changed = copy.deepcopy(value)
    changed['trust'] = 'provisional' if changed.get('trust') == 'low' else 'low'
    return changed


async def admit_capsule(runtime: Runtime, capsule: Capsule, *, model=None, contract=None, cases=None) -> dict:
    evidence, failures = [], []

    def record(name, ok, detail=''):
        evidence.append({'case': name, 'ok': bool(ok), 'detail': detail})
        if not ok:
            failures.append(name + (': ' + detail if detail else ''))

    result = {'capability_id': capsule.capability_id, 'key': capsule.key, 'version': capsule.version,
              'release_hash': capsule.release_hash, 'method': 'in_process_cases:1', 'passed': False,
              'evidence': evidence, 'failures': failures}
    if capsule.status != 'loaded':
        record('load', False, capsule.refusal_code + ': ' + capsule.reason)
        return result
    record('load_and_pins', True, 'pins verified and declaration built at load')
    declared = capsule.declaration['guarantees'].get('self_tests') or []
    if declared:
        record('declared_self_tests', False, '%d declared self-test(s) need the protected admission executor' % len(declared))
        return result
    record('declared_self_tests', True, 'none declared')
    plan = cases_for(capsule, cases)
    if plan is None:
        record('cases', False, 'no admission cases for this capsule; pass cases=... to admit()')
        return result
    needs_model = bool(capsule.declaration['needs']['injects'])
    if needs_model and model is None:
        # Admission tests the guards and the verifier around the worker, not the model. A canned
        # reply keeps it deterministic and free; the evidence says so.
        canned = plan.get('model_reply')
        if canned is None:
            record('model', False, 'model capsule: pass model= or give cases with a canned model_reply')
            return result

        async def model(prompt, system=None):
            return canned
        record('stub_model', True, 'canned worker reply used; model quality is not assessed by admission')
    if needs_model and not (contract or {}).get('objective'):
        contract = {**(contract or {}), 'objective': 'admission self-test'}

    async def run(inputs):
        return await runtime.ainvoke(capsule.key, inputs, worker_model=model, contract=contract, require_admission=False,
                                     _admitting=True)

    ports = capsule.ports_in()
    required = [p['name'] for p in ports if p['required']]
    positives = plan.get('positive') or []
    if not positives:
        record('positive_cases', False, 'at least one positive case is required')
    delivered = []
    for index, inputs in enumerate(positives):
        outcome = await run(inputs)
        ok = outcome['status'] == 'delivered' and outcome['receipt']['check_verdict'] == 'PASS'
        record('positive[%d]' % index, ok, '' if ok else json.dumps(outcome.get('halt'))[:300])
        if ok:
            delivered.append((inputs, outcome['outputs']))
    # Generic input-guard cases, derived from the declared ports only.
    for name in required:
        outcome = await run({k: v for k, v in (positives[0] if positives else {}).items() if k != name})
        record('guard_missing[%s]' % name, outcome['status'] == 'halted' and outcome['halt']['stage'] == 'input_guard'
               and outcome['halt']['code'] == 'missing_input', json.dumps(outcome.get('halt')))
    outcome = await run({name: {} for name in required})
    record('guard_malformed', outcome['status'] == 'halted' and outcome['halt']['stage'] == 'input_guard',
           json.dumps(outcome.get('halt')))
    for index, inputs in enumerate(plan.get('worker_halts') or []):
        outcome = await run(inputs)
        record('worker_halts[%d]' % index, outcome['status'] == 'halted' and outcome['halt']['stage'] == 'worker',
               json.dumps(outcome.get('halt')))
    # The verifier must bite: the same run with one output altered must halt at the verifier.
    # Deterministic capsules must reject both alterations; a model capsule's data
    # is free-form by design, so it passes if its verifier rejects at least one.
    def altering(change):
        return lambda outputs: {n: change(v) if isinstance(v, dict) and 'data' in v else v for n, v in outputs.items()}

    mutations = capsule.stage.mutations() if capsule.stage else {'data': altering(_tamper), 'trust': altering(_flip_trust)}
    for index, (inputs, outputs) in enumerate(delivered):
        if not capsule.stage and not any(isinstance(v, dict) and 'data' in v for v in outputs.values()):
            record('verifier_bites[%d]' % index, False, 'no packet output to alter; verifier not exercised')
            continue
        rejected = {}
        for label, mutate in mutations.items():
            outcome = await runtime.ainvoke(capsule.key, inputs, worker_model=model, contract=contract,
                                            require_admission=False, _mutate_outputs=mutate, _admitting=True)
            rejected[label] = outcome['status'] == 'halted' and outcome['halt']['stage'] == 'verifier'
        ok = all(rejected.values()) if not needs_model else any(rejected.values())
        record('verifier_bites[%d]' % index, ok, json.dumps(rejected))
    result['passed'] = not failures
    return result
