"""Source-backed capsule invocations, verifier outcomes, and node closure records."""
from __future__ import annotations

from collections import defaultdict
from math import isfinite
import re

from jiuwenswarm.factory import demo_board
from jiuwenswarm.factory.node_contract import from_contract
from .factory_nodes import bindings, recent_rows


INVOCATION_KINDS = {'cc_call', 'capsule_call', 'capability_call', 'tool_run', 'cc_tool_run'}
CAPPED_MODULE = 'jiuwenswarm.factory.capped_run'
PORTABLE_PATH = 'reports/evidence/factory-verification.json'
PORTABLE_SCHEMA = 'factory.muse-cc-activity/1'


def _time(value):
    if type(value) is int and abs(value) < 2**53:
        return value
    return value if type(value) is float and isfinite(value) else None


def _name(value):
    return value.split('@', 1)[0] if isinstance(value, str) and value else None


def _record(id, created, kind, path=None, **fields):
    when = _time(created)
    if isinstance(id, str) and id and when is not None:
        return dict(id=id, created=when, kind=kind, path=path, **fields)
    return None


def _explicit_cc(row):
    for key in ('cc', 'cc_id', 'capsule_id', 'capsule'):
        value = row.get(key)
        if isinstance(value, dict):
            value = value.get('id')
        if cc := _name(value):
            return cc
    return None


def _worker_scope(row):
    role = str(row.get('role') or row.get('actor') or '').lower().replace('_', '-')
    return role not in {'scheduler', 'scheduler-agent', 'verifier', 'node-verifier', 'cc-verifier'}


def archive_cutoff(data):
    task = data['tasks'][0]
    tid = task['task_id']
    dates = [task.get('created')]
    for kind in ('observations', 'decisions', 'attempts'):
        for row in data.get(kind, []):
            if row.get('task_id', tid) == tid:
                dates.extend(row.get(field) for field in ('created', 'started', 'ended'))
    return max((date for value in dates if (date := _time(value)) is not None), default=0)


def calls_as_of(calls, cutoff):
    result = []
    for call in calls:
        created, result_at = _time(call.get('created')), _time(call.get('result_at'))
        if created is None or created > cutoff:
            continue
        if result_at is not None and result_at > cutoff:
            # The call belongs to the export, but a later result cannot resolve its node, receipt or verdict.
            call = {key: value for key, value in call.items() if key not in {
                'verifier_passed', 'receipt_id', 'result_at', 'release', 'reason', 'state', 'failed', 'attempt_id',
            }} | dict(node_id=call.get('request_node_id'), state=None, reason=None, attempt_id=None)
        result.append(call)
    return result


def _merge_portable_rows(native, saved, cutoff, source_run_id, kind):
    by_id = {(row['kind'], row['id'], row.get('source_kind')): row for row in native}
    valid = {'worker-call', 'attempt', 'receipt'} if kind == 'uses' else {'cc-verifier'}
    for row in saved if isinstance(saved, list) else []:
        if not isinstance(row, dict) or row.get('kind') not in valid:
            continue
        if kind == 'verifier_records' and row.get('status') not in {'pass', 'fail'}:
            continue
        if row.get('source_run_id') not in (None, source_run_id):
            continue
        created, record_id = _time(row.get('created')), row.get('id')
        if created is None or created > cutoff or not isinstance(record_id, str) or not record_id:
            continue
        key = (row['kind'], record_id, row.get('source_kind'))
        if key not in by_id or not by_id[key].get('path'):
            by_id[key] = {key: row[key] for key in (
                'id', 'kind', 'created', 'capability', 'output', 'status', 'state', 'receipt_kind', 'source_kind',
            ) if key in row} | dict(path=PORTABLE_PATH, source_run_id=source_run_id)
    return sorted(by_id.values(), key=lambda row: row['created'])


def merge_portable(activity, saved, data, graph, origin_id):
    """Fill missing invocation/declaration records from a manifest-verified archived projection."""
    task = data['tasks'][0]
    if not isinstance(saved, dict) or saved.get('schema') != PORTABLE_SCHEMA:
        return activity
    origin = saved.get('source_run_id')
    cutoff = _time(saved.get('as_of'))
    nodes = saved.get('nodes')
    created = _time(task.get('created'))
    if (saved.get('task_id') != task['task_id'] or created is None or created <= 0
            or _time(saved.get('task_created')) != created or saved.get('graph_rev') != graph.get('rev')
            or not isinstance(origin, str) or not re.fullmatch(r'[a-f0-9]{24}', origin)
            or (origin_id is not None and origin != origin_id) or cutoff is None
            or cutoff < created or cutoff > archive_cutoff(data) or not isinstance(nodes, dict)):
        return activity
    for node_id, node in activity.items():
        stored_node = nodes.get(node_id)
        if not isinstance(stored_node, dict) or not isinstance(stored_node.get('capsules'), list):
            continue
        stored_ccs = {row['id']: row for row in stored_node['capsules']
                      if isinstance(row, dict) and isinstance(row.get('id'), str)}
        for cc in node['capsules']:
            saved_cc = stored_ccs.get(cc['id']) or {}
            saved_binding = saved_cc.get('bound_source') or {}
            binding = cc['bound_source'] or {}
            if (saved_cc.get('version') != cc['version'] or not isinstance(saved_binding, dict)
                    or saved_binding.get('id') != binding.get('id')
                    or saved_binding.get('created') != binding.get('created')):
                continue
            for key in ('uses', 'verifier_records'):
                cc[key] = _merge_portable_rows(cc[key], saved_cc.get(key), cutoff, origin, key)
            declaration = saved_cc.get('verifier_declaration')
            source = saved_cc.get('verifier_declaration_source')
            release = source.get('id') if isinstance(source, dict) else None
            if (cc['verifier_declaration'] == 'unknown' and declaration in {'declared', 'none'}
                    and isinstance(release, str) and re.fullmatch(r'[a-f0-9]{64}', release)):
                cc['verifier_declaration'] = declaration
                cc['verifier_declaration_source'] = dict(id=release, kind='sealed-release', path=PORTABLE_PATH)
    return activity


def _attempt_scope(data, nodes):
    task_id = data['tasks'][0]['task_id']
    attempts = {row['attempt_id']: row for row in data.get('attempts', [])
                if row.get('task_id', task_id) == task_id}
    node_ids = defaultdict(set)
    for node, row in nodes.items():
        for aid in row.get('attempt_ids', []):
            node_ids[aid].add(node)
    for aid, attempt in attempts.items():
        node = (attempt.get('request') or {}).get('node_id') or attempt.get('node_id')
        if node:
            node_ids[aid] = {node}
    return attempts, {aid: next(iter(names)) for aid, names in node_ids.items() if len(names) == 1}


def _invocations(data, node_ids, calls, paths, call_run_id, attempts, attempt_nodes):
    task_id = data['tasks'][0]['task_id']
    uses = defaultdict(list)
    linked_attempts = defaultdict(set)
    for call in calls:
        cc, node = _name(call.get('cc')), call.get('node_id')
        if cc and node in node_ids:
            source = _record(call.get('id'), call.get('created'), 'worker-call', paths.get('transcript'),
                             source_run_id=call_run_id, capability=call.get('capability'), state=call.get('state'))
            if source:
                uses[node, cc].append(source)
                aid = call.get('attempt_id')
                if aid in attempts and attempt_nodes.get(aid) == node:
                    linked_attempts[aid].add(cc)
    for row in data.get('observations', []):
        if row.get('task_id', task_id) != task_id:
            continue
        values, host = row.get('values') or {}, row.get('host_run') or {}
        kind = row.get('kind')
        if kind == 'capped_run' and host.get('module') == CAPPED_MODULE:
            cc = 'factory.capped_runner'
        elif kind == 'build_result' and host.get('jobq_id') and (host.get('receipt') or {}).get('build_record'):
            cc = 'factory.builder'
        elif kind in INVOCATION_KINDS and _worker_scope(values) and _worker_scope(host):
            cc = _explicit_cc(values) or _explicit_cc(row)
        else:
            continue
        aid = values.get('attempt_id') or host.get('attempt_id')
        request = values.get('request') or {}
        attempt_node = attempt_nodes.get(aid)
        node = values.get('node_id') or request.get('node_id') or attempt_node
        if not cc or node not in node_ids or (attempt_node and node != attempt_node):
            continue
        source = _record(row.get('obs_id'), row.get('created'), 'receipt', paths.get('observations'),
                         capability=values.get('capability') or values.get('recipe'), receipt_kind=kind)
        if source:
            uses[node, cc].append(source)
            if aid in attempts and attempt_node == node:
                linked_attempts[aid].add(cc)
    for aid, row in attempts.items():
        request = row.get('request') or {}
        node = attempt_nodes.get(aid)
        if node not in node_ids or not _worker_scope(request) or row.get('kind') in {'node_check', 'scheduler'}:
            continue
        ccs = set(linked_attempts.get(aid, ()))
        if cc := _explicit_cc(request) or _explicit_cc(row):
            ccs.add(cc)
        history = row.get('history') or []
        started = next((item.get('created') for item in history if _time(item.get('created')) is not None), row.get('started'))
        for cc in ccs:
            source = _record(aid, started, 'attempt', paths.get('attempts'),
                             capability=request.get('capability') or request.get('recipe'))
            if source:
                uses[node, cc].append(source)
    return uses


def _closures(data, graph, path):
    result = defaultdict(list)
    unbound = {}
    history = graph.get('history', [])
    graphs, _ = demo_board.replay_graph(history)
    sources = {row['values']['rev']: row for row in recent_rows(data, 'taskgraph_patch')}
    task_id = data['tasks'][0]['task_id']
    decisions = {r.get('rev'): r['decision_id'] for r in data.get('decisions', [])
                 if r.get('task_id', task_id) == task_id and r.get('decision_id')}
    for entry in history:
        rev = entry['rev']
        row = sources.get(rev)
        if not row:
            continue
        before, after = graphs.get(rev - 1, {}), graphs.get(rev, {})
        by = decisions.get(entry.get('decision_rev')) if entry.get('origin') == 'decision' else None
        for node_id, node in after.items():
            prior = before.get(node_id, {})
            if (old := prior.get('final_contract')) and old != node.get('final_contract'):
                source = _record(row.get('obs_id'), row.get('created'), 'graph-patch', path, origin=entry.get('origin'))
                if source:
                    unbound[node_id, old] = source
            was_done = prior.get('state') == 'done'
            done = node.get('state') == 'done'
            if was_done == done:
                continue
            item = _record(row.get('obs_id'), row.get('created'), 'graph-patch', path,
                           state='done' if done else 'reopened', decision_id=by, origin=entry.get('origin'),
                           evidence_ids=node.get('evidence_ids', []) if done else [])
            if item:
                result[node_id].append(item)
    return result, unbound


def _declared_verifiers(contract):
    return {capability for row in (contract or {}).get('verifiers') or []
            if isinstance(capability := row.get('verifier'), str)}


def _release_verifiers(releases, cc, version, preferred, explicit):
    manifests = releases.get((cc, version), [])
    matched = [row for row in manifests if row[0] in preferred]
    choices = matched or manifests
    if len(choices) != 1:
        return 'unknown', None, set()
    release, manifest = choices[0]
    capabilities = (manifest.get('declaration') or {}).get('capabilities')
    if not isinstance(capabilities, dict):
        return 'unknown', None, set()
    verifier_names = {name for name in capabilities
                      if name == 'verify' or name.startswith('verify_') or f'{cc}.{name}' in explicit}
    declared = 'declared' if verifier_names else 'none'
    return declared, dict(id=release, kind='sealed-release'), verifier_names


def project(data, graph, calls=(), releases=None, paths=None, call_run_id=None):
    paths = paths or {}
    releases = releases or {}
    nodes = {node['node_id']: node for node in graph.get('nodes', [])}
    attempts, attempt_nodes = _attempt_scope(data, nodes)
    scoped_calls = []
    for call in calls:
        node, linked = call.get('node_id'), attempt_nodes.get(call.get('attempt_id'))
        if node and linked and node != linked:
            continue
        if node or linked:
            scoped_calls.append(dict(call, node_id=node or linked))
    authored = {row['node_id']: row for row in (from_contract(data.get('_contract') or {}) or {}).get('nodes', [])}
    finalisations = defaultdict(list)
    for row in recent_rows(data, 'node_contract_final'):
        finalisations[row['values'].get('node_id')].append(row)
    node_checks, cc_checks = defaultdict(list), defaultdict(list)
    for row in recent_rows(data, 'node_check'):
        value = row['values']
        node = value.get('node_id')
        if node not in nodes or value.get('state') != 'finished':
            continue
        verifier = value.get('verifier') or {}
        if type(value.get('passed')) is bool:
            node_check = _record(row.get('obs_id'), row.get('created'), 'node-check', paths.get('observations'),
                                 output=value.get('output', 'change'), status='pass' if value['passed'] else 'fail')
            if node_check:
                node_checks[node].append(node_check)
        if (cc := _name(verifier.get('cc'))) and type(verifier.get('passed')) is bool:
            cc_check = _record(row.get('obs_id'), row.get('created'), 'cc-verifier', paths.get('observations'),
                               output=value.get('output', 'change'), status='pass' if verifier['passed'] else 'fail',
                               release=verifier.get('release'), capability=verifier.get('capability'),
                               source_kind='node-check')
            if cc_check:
                cc_checks[node, cc].append(cc_check)
    uses = _invocations(data, nodes, scoped_calls, paths, call_run_id, attempts, attempt_nodes)
    closures, unbound = _closures(data, graph, paths.get('observations'))
    result = {}
    for node, details in nodes.items():
        binding_rows = defaultdict(list)
        explicit = set()
        for row in finalisations[node]:
            explicit.update(_declared_verifiers(row['values'].get('final')))
            final_digest = row['values'].get('digest')
            for cc, version in bindings(row):
                source = _record(row.get('obs_id'), row.get('created'), 'node-contract-final', paths.get('observations'))
                if source:
                    end = unbound.get((node, final_digest))
                    binding_rows[cc].append(dict(version=version, source=source, final_digest=final_digest,
                                                 unbound_at=end['created'] if end else None, unbound_source=end))
        current_contract = authored.get(details.get('node_contract') or node) or {}
        if current_contract.get('stage') == 'final' and not finalisations[node]:
            explicit.update(_declared_verifiers(current_contract))
            for cc, version in bindings(None, current_contract):
                binding_rows[cc].append(dict(version=version, source=None, final_digest=None))
        capsule_rows = []
        for cc, bound in binding_rows.items():
            version = bound[-1]['version']
            relevant_calls = [c for c in scoped_calls if c.get('node_id') == node and _name(c.get('cc')) == cc]
            preferred = {r.get('release') for r in relevant_calls} | {r.get('release') for r in cc_checks[node, cc]}
            declaration, declaration_source, verify_names = _release_verifiers(releases, cc, version, preferred, explicit)
            verifier_records = list(cc_checks[node, cc])
            for call in relevant_calls:
                capability = call.get('capability')
                if ((capability in verify_names or f'{cc}.{capability}' in explicit)
                        and type(call.get('verifier_passed')) is bool):
                    source = _record(call.get('id'), call.get('result_at'), 'cc-verifier', paths.get('transcript'),
                                     source_run_id=call_run_id, source_kind='worker-call', capability=capability,
                                     status='pass' if call['verifier_passed'] else 'fail')
                    if source:
                        verifier_records.append(source)
            bound_source = bound[0]['source']
            capsule_rows.append(dict(
                id=cc, version=version, bound_at=bound_source['created'] if bound_source else None,
                bound_source=bound_source, bindings=bound, unbound_at=bound[-1].get('unbound_at'),
                active=any(row['final_digest'] == details.get('final_contract') for row in bound),
                verifier_declaration=declaration, verifier_declaration_source=declaration_source,
                uses=sorted(uses[node, cc], key=lambda row: row['created']),
                verifier_records=sorted(verifier_records, key=lambda row: row['created']),
            ))
        result[node] = dict(capsules=capsule_rows, closures=closures[node], node_checks=node_checks[node])
    return result
