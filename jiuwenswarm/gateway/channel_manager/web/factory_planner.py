"""Planner and scheduler evidence projected from committed Factory records."""
from __future__ import annotations

from hashlib import sha256
import json

from jiuwenswarm.factory.demo_board import rebuild_preliminary
from jiuwenswarm.factory.node_contract import check_spec, from_contract
from jiuwenswarm.factory.node_finalize import digest, is_preliminary
from jiuwenswarm.factory.redact import sanitize


ARTIFACT_PATH = 'projections/planner-plan.json'
TERMINAL = {'cancelled', 'superseded'}
READ_KINDS = {'planner_read', 'planner_reads', 'planner_read_receipt', 'planner_read_receipts'}


def _source(row, path, **extra):
    return dict(id=row['obs_id'], path=path, created=row.get('created'), **extra)


def _contract_nodes(value):
    return {node['node_id']: node for node in (from_contract(value) or {}).get('nodes', [])
            if is_preliminary(node)}


def _index_contracts(data, contracts, amendments, allow_run_contract):
    """Join by native node digest. Keep the pre-amendment contract distinct from active versions."""
    indexed = {}
    current = data.get('_contract')
    active = next((row for row in contracts if row['document'] == current), None)
    if current and not active and allow_run_contract:
        active = dict(document=current, source=dict(kind='run-contract', id=current.get('contract_id'), path=None))
        contracts = [*contracts, active]
    if amendments:
        original_sha = amendments[0]['values'].get('previous_sha256')
        original = next((row for row in contracts if original_sha and row['source'].get('sha256') == original_sha), None)
    else:
        original = active
    for row in ([original] if original else []) + [row for row in contracts if row is not original]:
        for name, node in _contract_nodes(row['document']).items():
            expected = digest(node)
            indexed.setdefault((name, expected), (node, dict(row['source'], digest=expected)))
    original_drafts = {}
    if original:
        for name, node in _contract_nodes(original['document']).items():
            original_drafts[name] = (node, dict(original['source'], digest=digest(node)))
    return indexed, original_drafts


def _preliminary(indexed, name, expected, final, changes, source):
    if not isinstance(expected, str) or not expected:
        return None, None
    if (known := indexed.get((name, expected))) is not None:
        return known
    if isinstance(final, dict) and isinstance(changes, list):
        try:
            reconstructed = rebuild_preliminary(final, changes)
            if is_preliminary(reconstructed) and digest(reconstructed) == expected:
                return reconstructed, dict(source, kind='diff-reconstruction', digest=expected)
        except (ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass  # Keep the recorded diff when its before values do not reproduce the draft.
    return None, None


def _matches_seed(draft, node):
    if 'check' not in node:
        return True
    try:
        return node['check'] == check_spec(draft)
    except (TypeError, KeyError, AttributeError):
        return False


def _finals(observations, contract_index, path):
    result, refusals = {}, {}
    for row in observations:
        values = row.get('values') or {}
        node_id = values.get('node_id')
        if not node_id or row['kind'] not in {'node_contract_final', 'node_contract_refusal'}:
            continue
        source = _source(row, path)
        if row['kind'] == 'node_contract_refusal':
            refusals.setdefault(node_id, []).append(dict(
                source, problems=values.get('problems'), rationale=values.get('rationale'), by=values.get('by'),
                proposal_digest=values.get('proposal_digest'),
                never_weaker=dict(status='refused', source=source),
            ))
            continue
        final, changes = values.get('final'), values.get('diff')
        expected = values.get('preliminary_digest')
        preliminary, draft_source = _preliminary(
            contract_index, values.get('node_contract') or node_id, expected, final, changes, source,
        )
        # The scheduler writes the final observation only after the host's never-weaker admission.
        status = 'admitted' if isinstance(final, dict) and digest(final) == values.get('digest') else 'unverified'
        result.setdefault(node_id, []).append(dict(
            source, preliminary_digest=expected, digest=values.get('digest'), preliminary=preliminary,
            preliminary_source=draft_source, final=final, diff=changes, rationale=values.get('rationale'),
            by=values.get('by'), cc_versions=values.get('cc_versions'), never_weaker=dict(status=status, source=source),
        ))
    return result, refusals


def _changes(observations, path):
    completed, added, removed, updated = {}, {}, {}, {}
    for row in observations:
        if row['kind'] != 'taskgraph_patch':
            continue
        values = row.get('values') or {}
        patch = values.get('patch') or {}
        source = _source(row, path, revision=values.get('rev'), origin=values.get('origin'))
        for node in patch.get('update', []):
            if node.get('state') == 'done':
                completed.setdefault(node['node_id'], source)
            if 'depends_on' in node:
                updated[node['node_id']] = source
            if node.get('state') in TERMINAL:
                removed[node['node_id']] = source
        for op in ('cancel', 'supersede', 'retire'):
            removed.update({node['node_id']: source for node in patch.get(op, [])})
        for node in patch.get('revise', []):
            if node.get('action') == 'add':
                added[node['node_id']] = source
            elif node.get('action') == 'cancel':
                removed[node['node_id']] = source
            elif 'depends_on' in node:
                updated[node['node_id']] = source
        if values.get('origin') != 'seed':
            added.update({node['node_id']: source for node in patch.get('add', [])})
    return completed, added, removed, updated


def _read_receipts(observations, seed, path):
    time = seed.get('created')
    linked = {item for item in (seed['values'].get('read_receipt_ids') or []) if isinstance(item, str)}
    receipts = [dict(_source(row, path), kind=row['kind'], values=row.get('values'))
                for row in observations if row['kind'] in READ_KINDS or row['obs_id'] in linked
                if time is None or (row.get('created') or 0) <= time]
    embedded = seed['values'].get('read_receipts')
    if isinstance(embedded, list) and embedded:
        receipts.append(dict(_source(seed, path), kind='planner_read_receipts', values=embedded))
    return receipts


def artifact_file(document):
    content = json.dumps(sanitize(document), indent=2, ensure_ascii=False, sort_keys=True) + '\n'
    blob = content.encode()
    return dict(path=ARTIFACT_PATH, display_path='Planner plan and rough node contracts',
                media_type='application/json', artifact_ids=[], integrity='untracked',
                sha256=sha256(blob).hexdigest(), expected_sha256=None, size=len(blob),
                content=content, truncated=False)


def project(data, graph, contracts, observation_path=None, *, allow_run_contract=True):
    task_id = data['tasks'][0]['task_id']
    observations = sorted((row for row in data.get('observations', []) if row.get('task_id', task_id) == task_id),
                          key=lambda row: row.get('created') or 0)
    seed = next((row for row in observations if row['kind'] == 'taskgraph_patch'
                 and (row.get('values') or {}).get('origin') == 'seed'), None)
    if seed is None:
        return None
    values = seed['values']
    source = _source(seed, observation_path, revision=values.get('rev'), planner=values.get('planner'))
    plan_nodes = {row['node_id']: row for row in (values.get('patch') or {}).get('add', [])}
    active = {node['node_id']: node for node in graph.get('nodes', [])}
    amendments = [row for row in observations if row['kind'] == 'operator_contract_revision']
    contract_index, initial_drafts = _index_contracts(data, contracts, amendments, allow_run_contract)
    finals, refusals = _finals(observations, contract_index, observation_path)
    completed, added, removed, updated = _changes(observations, observation_path)
    run_order = sorted((name for name, row in active.items() if row.get('state') not in TERMINAL),
                       key=lambda name: (completed.get(name) or {}).get('revision') or float('inf'))
    receipts = _read_receipts(observations, seed, observation_path)
    nodes = []
    for name in dict.fromkeys([*plan_nodes, *active]):
        before, after = plan_nodes.get(name), active.get(name)
        contract_name = (before or {}).get('node_contract')
        draft, draft_source = initial_drafts.get(contract_name, (None, None)) if before else (None, None)
        pinned = (before or {}).get('preliminary_digest')
        if pinned and (draft_source or {}).get('digest') != pinned:
            draft, draft_source = contract_index.get((contract_name, pinned), (None, None))
        if draft and not pinned and not _matches_seed(draft, before):
            draft, draft_source = None, None
        record = (before or after or {})
        work = (draft or {}).get('work') or {}
        suggested = work.get('helpful_ccs') or []
        change, change_source = 'unchanged', None
        if before and name in removed and (after is None or after.get('state') in TERMINAL):
            change, change_source = 'removed', removed.get(name)
        elif before is None and name in added:
            change, change_source = 'added', added.get(name)
        elif before and after and name in updated and set(before.get('depends_on', [])) != set(after.get('depends_on', [])):
            change, change_source = 'reordered', updated[name]
        nodes.append(dict(node_id=name, title=record.get('title'), change=change, change_source=change_source,
                          draft=draft, draft_source=draft_source, suggested_ccs=suggested,
                          finals=finals.get(name, []), refusals=refusals.get(name, [])))
    document = dict(schema='factory.planner-plan/1', task_id=task_id, source=source, read_receipts=receipts,
                    nodes=[dict(graph_node=plan_nodes[row['node_id']], draft=row['draft'],
                                draft_source=row['draft_source'], suggested_ccs=row['suggested_ccs'])
                           for row in nodes if row['node_id'] in plan_nodes])
    file = artifact_file(document)
    artifact = {key: value for key, value in file.items() if key not in {'content', 'truncated'}}
    return dict(artifact=artifact, source=source, plan_order=list(plan_nodes), run_order=run_order,
                read_receipts=receipts, nodes=nodes, _file=file)
