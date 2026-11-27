"""Source-backed capsule invocations, verifier outcomes, and node closure records."""
from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from math import isfinite
import re
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile

from jiuwenswarm.factory import demo_board
from jiuwenswarm.factory.node_contract import from_contract
from .factory_nodes import bindings, recent_rows


INVOCATION_KINDS = {'cc_call', 'capsule_call', 'capability_call', 'tool_run', 'cc_tool_run'}
CAPPED_MODULE = 'jiuwenswarm.factory.capped_run'
PORTABLE_PATH = 'reports/evidence/factory-verification.json'
PORTABLE_SCHEMA = 'factory.muse-cc-activity/1'
WORK_DECISIONS = {'inspect', 'investigate', 'integrate', 'build', 'measure', 'tune', 'deliver'}
PLANNING_KINDS = {'taskgraph_patch', 'node_contract_final', 'node_contract_refusal', 'operator_contract_revision'}
SEARCH_FIELDS = ('worker_calls', 'attempts', 'observations', 'node_checks', 'decisions', 'ccstore_calls', 'operator_imports')
REACHED_KINDS = {'worker-call', 'attempt', 'node-check', 'decision', 'receipt', 'cc-verifier', 'graph-patch'}


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


def _capability_cc(value):
    return _name(value.rpartition('.')[0]) if isinstance(value, str) else None


def ccstore_calls(path, releases):
    if not path.is_file():
        return None
    index = {release: cc for (cc, _), rows in releases.items() for release, _ in rows}
    result = []
    files = (path, path.with_name(path.name + '-wal'))

    def stamps():
        result = []
        for file in files:
            try:
                if file.is_symlink():
                    raise OSError('unexpected ccstore symlink')
                status = file.stat()
                result.append((status.st_ino, status.st_size, status.st_mtime_ns))
            except FileNotFoundError:
                result.append(None)
        return result

    try:
        # Reading a live WAL directly can create SQLite -shm files in the run.
        # SQLite only sees our private copy, and applies the copied WAL normally.
        with tempfile.TemporaryDirectory(prefix='factory-cc-activity-') as directory:
            local = Path(directory) / path.name
            for _ in range(5):
                before = stamps()
                try:
                    for file, stamp in zip(files, before):
                        target = local.with_name(file.name)
                        if stamp:
                            shutil.copyfile(file, target)
                        else:
                            target.unlink(missing_ok=True)
                except FileNotFoundError:
                    continue
                if before == stamps():
                    break
            else:
                return None
            with closing(sqlite3.connect(local.as_uri() + '?mode=ro', uri=True)) as db:
                rows = list(db.execute('SELECT receipt FROM calls'))
            for raw, in rows:
                receipt = json.loads(raw)
                provenance = receipt.get('provenance') or {}
                inputs = provenance.get('inputs') or {}
                request = inputs.get('request') or {}
                output = (receipt.get('outputs') or {}).get('result') or {}
                request = request if isinstance(request, dict) else {}
                output = output if isinstance(output, dict) else {}
                cc = index.get(receipt.get('release')) or _explicit_cc(provenance)
                created = _time(provenance.get('started'))
                if cc and created is not None and receipt.get('call'):
                    result.append(dict(id=receipt['call'], cc=cc, capability=receipt.get('capability'), created=created,
                                       node_id=inputs.get('node_id') or request.get('node_id') or output.get('node_id'),
                                       task_id=inputs.get('task_id') or request.get('task_id') or output.get('task_id'),
                                       state=receipt.get('state')))
    except (OSError, ValueError, sqlite3.Error):
        return None
    return result


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
    valid = {'worker-call', 'attempt', 'receipt', 'cc-verifier'} if kind == 'uses' else {'cc-verifier'}
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
                               'invocation_id', 'artifact_id',
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
            known_uses = {row['id'] for row in cc['uses']}
            for record in cc['verifier_records']:
                if record['id'] not in known_uses:
                    cc['uses'].append(record)
                    known_uses.add(record['id'])
            cc['uses'].sort(key=lambda row: row['created'])
            declaration = saved_cc.get('verifier_declaration')
            source = saved_cc.get('verifier_declaration_source')
            release = source.get('id') if isinstance(source, dict) else None
            if (cc['verifier_declaration'] == 'unknown' and declaration in {'declared', 'none'}
                    and isinstance(release, str) and re.fullmatch(r'[a-f0-9]{64}', release)):
                cc['verifier_declaration'] = declaration
                cc['verifier_declaration_source'] = dict(id=release, kind='sealed-release', path=PORTABLE_PATH)
        evidence = [source for cc in node['capsules'] for source in cc['uses']]
        if node.get('reached'):
            evidence.append(node['reached'])
        saved_reached = stored_node.get('reached')
        if (isinstance(saved_reached, dict) and saved_reached.get('kind') in REACHED_KINDS
                and (at := _time(saved_reached.get('created'))) is not None and at <= cutoff):
            source = _record(saved_reached.get('id'), at, saved_reached.get('kind'), PORTABLE_PATH, source_run_id=origin)
            if source:
                evidence.append(source)
        node['reached'] = min(evidence, key=lambda row: row['created'], default=None)
        searched = stored_node.get('searched')
        if isinstance(searched, dict):
            for key in SEARCH_FIELDS:
                if isinstance(values := searched.get(key), list):
                    node['searched'][key] = list(dict.fromkeys([*node['searched'][key],
                                                               *(value for value in values if isinstance(value, str))]))
            availability = searched.get('source_availability')
            for key in ('worker_transcript', 'ccstore'):
                if isinstance(availability, dict) and availability.get(key) is True:
                    node['searched']['source_availability'][key] = True
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
        if cc := _explicit_cc(request) or _explicit_cc(row) or _capability_cc(request.get('capability')):
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


def _activity_sources(data, nodes, closures, paths, attempts, attempt_nodes, calls, receipts,
                      call_run_id, receipt_run_id, allow_untagged, source_availability):
    tid = data['tasks'][0]['task_id']
    searched = {node: {key: [] for key in SEARCH_FIELDS} | dict(source_availability=source_availability.copy())
                for node in nodes}
    reached, additions, references, receipt_links = defaultdict(list), defaultdict(list), defaultdict(dict), {}
    scoped_receipts = {}

    def note(node, source, category, execution=False):
        if node in nodes and source:
            searched[node][category].append(source['id'])
            if execution:
                reached[node].append(source)

    def cite(node, keys, created):
        if node in nodes:
            for key in keys:
                if isinstance(key, str):
                    fields = references[key]
                    fields[node] = min(fields.get(node, created), created)

    for call in calls:
        node = call.get('node_id')
        source = _record(call.get('id'), call.get('created'), 'worker-call', paths.get('transcript'),
                         source_run_id=call_run_id, capability=call.get('capability'))
        note(node, source, 'worker_calls', execution=True)
        if call.get('receipt_id') and node in nodes:
            receipt_links[call['receipt_id']] = node, _name(call.get('cc'))

    for aid, attempt in attempts.items():
        start = attempt.get('started')
        requested = next((row.get('created') for row in (attempt.get('history') or []) if _time(row.get('created')) is not None), start)
        note(attempt_nodes.get(aid), _record(aid, requested, 'attempt', paths.get('attempts')),
             'attempts', execution=attempt.get('kind') != 'scheduler' and _worker_scope(attempt.get('request') or {}))
    for action_record in data.get('decisions', []):
        if action_record.get('task_id', tid) != tid:
            continue
        action = action_record.get('action') or {}
        node = action.get('node_id')
        note(node, _record(action_record.get('decision_id'), action_record.get('created'), 'decision',
                           paths.get('decisions'), action=action.get('type')), 'decisions',
             execution=action.get('type') in WORK_DECISIONS)
    observations = [row for row in data.get('observations', []) if row.get('task_id', tid) == tid]
    for row in observations:
        values = row.get('values') or {}
        kind = row.get('kind')
        node = values.get('node_id') or attempt_nodes.get(values.get('attempt_id') or (row.get('host_run') or {}).get('attempt_id'))
        source = _record(row.get('obs_id'), row.get('created'), 'node-check' if kind == 'node_check' else 'receipt',
                         paths.get('observations'), receipt_kind=kind)
        note(node, source, 'node_checks' if kind == 'node_check' else 'observations', execution=kind == 'node_check')
        if kind == 'node_check' and node in nodes and source:
            refs = values.get('refs') or {}
            cite(node, [*(refs.get('evidence_ids') or []), *(refs.get('artifact_ids') or [])], source['created'])
            verifier = values.get('verifier')
            cc = ((_name(verifier.get('cc')) or _capability_cc(verifier.get('capability')))
                  if isinstance(verifier, dict) else _capability_cc(verifier))
            cc = cc or _capability_cc(values.get('capability'))
            call = verifier.get('call') if isinstance(verifier, dict) else None
            verdict = isinstance(verifier, dict) and type(verifier.get('passed')) is bool
            recorded_capability = values.get('capability') or (verifier if isinstance(verifier, str) else None)
            if cc and (call or verdict or (recorded_capability and values.get('state') == 'finished')):
                if call:
                    receipt_links[call] = node, cc
                additions[node, cc].append(dict(source, kind='cc-verifier', source_kind='node-check',
                                                invocation_id=call, output=values.get('output'),
                                                capability=verifier.get('capability') if isinstance(verifier, dict)
                                                else recorded_capability))

    for node, facts in closures.items():
        for fact in facts:
            cite(node, fact['evidence_ids'], fact['created'])
    for receipt in receipts:
        cc, node = receipt['cc'], receipt.get('node_id')
        linked_node, linked_cc = receipt_links.get(receipt['id'], (None, None))
        if receipt.get('task_id') not in (None, tid) or (linked_cc and cc != linked_cc):
            continue
        if linked_node:
            if node and linked_node != node:
                continue
            node = linked_node
        elif not (receipt.get('task_id') == tid or allow_untagged):
            continue
        if node not in nodes:
            continue
        source = _record(receipt['id'], receipt.get('created'), 'receipt', None, source_kind='ccstore',
                         source_run_id=receipt_run_id, capability=receipt.get('capability'), state=receipt.get('state'))
        if source:
            additions[node, cc].append(source)
            scoped_receipts[receipt['id']] = node, cc
            note(node, source, 'ccstore_calls', execution=True)

    artifacts = {artifact['artifact_id']: artifact for artifact in data.get('artifacts', [])
                 if artifact.get('task_id', tid) == tid}
    for row in observations:
        if row.get('kind') != 'operator_input':
            continue
        refs = row.get('values') or {}
        artifact_id = refs.get('artifact_id')
        attached = set(row.get('source_artifacts') or [])
        producer = refs.get('producer') or (row.get('host_run') or {}).get('producer') or {}
        producer = producer if isinstance(producer, dict) else {}
        cc = (_explicit_cc(producer) or _explicit_cc(refs) or _name(refs.get('producer_cc'))
              or _capability_cc(producer.get('capability') or refs.get('producer_capability')))
        nodes_read = {}
        for key in (row.get('obs_id'), artifact_id, *attached):
            for node, created in references.get(key, {}).items():
                nodes_read[node] = min(nodes_read.get(node, created), created)
        explicit_node = refs.get('node_id')
        if explicit_node in nodes:
            nodes_read[explicit_node] = row.get('created')
        for node, cited in nodes_read.items():
            base = _record(row.get('obs_id'), row.get('created'), 'receipt', paths.get('observations'),
                           artifact_id=artifact_id, receipt_kind='operator_input')
            note(node, base, 'operator_imports')
            if not base or not artifact_id or artifact_id not in attached:
                continue
            aid = artifacts.get(artifact_id, {}).get('producer_attempt')
            attempt = attempts.get(aid) or {}
            scoped_cc = cc
            if not scoped_cc and attempt_nodes.get(aid) == node:
                invocation = attempt.get('request') or {}
                scoped_cc = _explicit_cc(invocation) or _explicit_cc(attempt) or _capability_cc(invocation.get('capability'))
            if not scoped_cc and (native := scoped_receipts.get(aid)) and native[0] == node:
                scoped_cc = native[1]
            if scoped_cc and producer.get('node_id') in (None, node):
                source = dict(base, created=max(base['created'], _time(cited) or base['created']),
                              capability=producer.get('capability') or refs.get('capability'))
                additions[node, scoped_cc].append(source)
                reached[node].append(source)
    return reached, searched, additions


def project(data, graph, calls=(), releases=None, paths=None, call_run_id=None, *,
            receipts=(), receipt_run_id=None, allow_untagged=False, source_availability=None):
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
        verifier = value.get('verifier')
        if type(value.get('passed')) is bool:
            node_check = _record(row.get('obs_id'), row.get('created'), 'node-check', paths.get('observations'),
                                 output=value.get('output', 'change'), status='pass' if value['passed'] else 'fail')
            if node_check:
                node_checks[node].append(node_check)
        if (isinstance(verifier, dict) and (cc := _name(verifier.get('cc')))
                and type(verifier.get('passed')) is bool):
            cc_check = _record(row.get('obs_id'), row.get('created'), 'cc-verifier', paths.get('observations'),
                               output=value.get('output', 'change'), status='pass' if verifier['passed'] else 'fail',
                               release=verifier.get('release'), capability=verifier.get('capability'),
                               source_kind='node-check')
            if cc_check:
                cc_checks[node, cc].append(cc_check)
    uses = _invocations(data, nodes, scoped_calls, paths, call_run_id, attempts, attempt_nodes)
    closures, unbound = _closures(data, graph, paths.get('observations'))
    reached, searched, additions = _activity_sources(
        data, nodes, closures, paths, attempts, attempt_nodes, scoped_calls, receipts, call_run_id,
        receipt_run_id or call_run_id,
        allow_untagged, source_availability or dict(worker_transcript=bool(calls), ccstore=bool(receipts)),
    )
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
            capsule_uses = [*uses[node, cc], *additions[node, cc]]
            reached[node].extend(capsule_uses)
            capsule_rows.append(dict(
                id=cc, version=version, bound_at=bound_source['created'] if bound_source else None,
                bound_source=bound_source, bindings=bound, unbound_at=bound[-1].get('unbound_at'),
                active=any(row['final_digest'] == details.get('final_contract') for row in bound),
                verifier_declaration=declaration, verifier_declaration_source=declaration_source,
                uses=sorted(capsule_uses, key=lambda row: row['created']),
                verifier_records=sorted(verifier_records, key=lambda row: row['created']),
            ))
        reached[node].extend(source for source in closures[node] if source['state'] == 'done')
        result[node] = dict(capsules=capsule_rows, closures=closures[node], node_checks=node_checks[node],
                            reached=min(reached[node], key=lambda row: row['created'], default=None),
                            searched={key: list(dict.fromkeys(value)) if isinstance(value, list) else value
                                      for key, value in searched[node].items()})
    return result
