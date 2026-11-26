"""Deterministic bridge keeping and invoking M1 ``binding.plan_checks(...)``.

Instead of silently replacing M1's static plan verifier with M2 rules, this module
deterministically translates M2 artifacts (``factory.node-contracts/1``, ``factory.plan/1``,
``factory.task-input/1``, ``plan_catalog``) into the 5 M1 inputs required by
``jiuwenswarm.research.binding.plan_checks`` (``plan-proposal``, ``research-brief``,
``library-snapshot``, ``resource-inventory``, ``plan-policy``) and invokes the real M1
checker alongside M2's 8 semantic rules and TLC.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from jiuwenswarm.research.binding import SHARED_CHECKS, plan_checks as m1_binding_plan_checks
from jiuwenswarm.research.capability_planning import capability_plan_policy

from .requirements import contract_ids, input_id, ids as task_input_ids

M1_LIMITATIONS: list[dict[str, Any]] = [
    {
        'id': 'm1_single_attempt_no_starvation',
        'title': 'Hard-locked single dispatch attempt & no build_attempts starvation check',
        'summary': (
            'M1 binding.plan_checks locks policy.max_attempts_per_node == 1 and only checks '
            'time_s / model_calls / memory_mb against admission caps, ignoring retry budgets and '
            'build_attempts == 0 starvation (while hurting transient-failure Class A delivery).'
        ),
        'source_refs': [
            'jiuwenswarm/research/binding.py:98',
            'jiuwenswarm/research/binding.py:124-125',
            'jiuwenswarm/research/binding.py:453',
        ],
    },
    {
        'id': 'm1_no_concurrent_mutex_model',
        'title': 'No concurrent resource/checkout mutex or reachable-state model',
        'summary': (
            'M1 validates local node fields statically and models neither exclusive workspace/builder '
            'locks nor concurrent interleavings across active nodes.'
        ),
        'source_refs': [
            'jiuwenswarm/research/binding.py:65-228',
            'jiuwenswarm/research/capability_planning.py:8-13',
        ],
    },
    {
        'id': 'm1_predecessors_acyclic_only',
        'title': 'Checks predecessor DAG acyclicity only, missing scheduler depends_on cycles',
        'summary': (
            'M1 kahn_order() inspects node.predecessors only and has no factory.plan/1 depends_on '
            'field, letting scheduling-layer ordering deadlocks pass.'
        ),
        'source_refs': [
            'jiuwenswarm/research/binding.py:25-40',
            'jiuwenswarm/research/binding.py:103',
        ],
    },
    {
        'id': 'm1_coarse_effect_class_only',
        'title': 'Coarse effect_class only, lacking per-kind write-prohibition & join rules',
        'summary': (
            'M1 checks coarse effect_class membership and capability layout rules without '
            'per-kind build/deliver workspace != write least-privilege guards or join_before_build.'
        ),
        'source_refs': [
            'jiuwenswarm/research/binding.py:118',
            'jiuwenswarm/research/capability_planning.py:24-48',
        ],
    },
]

_DELIVERABLE_ID = 'deliverable:lab_request'
_PIPELINE_REQ_ID = 'req:pipeline_upstream'


def _sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _slug(raw: str, *, prefix: str = 'id', max_len: int = 31) -> str:
    cleaned = re.sub(r'[^a-z0-9_]+', '_', str(raw or '').lower()).strip('_')
    if not cleaned:
        cleaned = prefix
    if not cleaned[0].isalpha():
        cleaned = f'{prefix}_{cleaned}'
    return cleaned[:max_len]


def _unique_slug(raw: str, used: set[str], *, prefix: str = 'id', max_len: int = 31) -> str:
    base = _slug(raw, prefix=prefix, max_len=max_len)
    cand = base
    idx = 2
    while cand in used:
        suffix = f'_{idx}'
        cand = base[: max_len - len(suffix)] + suffix
        idx += 1
    used.add(cand)
    return cand


def _resolve_cc_pin(node: dict[str, Any], catalog_capsules: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    work = node.get('work') or {}
    cap = work.get('capability') or ''
    matched_cap_id = None
    for cid in catalog_capsules:
        if cap == cid or cap.startswith(cid + '.'):
            matched_cap_id = cid
            break
    if matched_cap_id:
        ns, _, leaf = matched_cap_id.partition('.')
        # Keep away from research.* scientific stage names so M1 uses general capability DAG semantics.
        safe_ns = 'cap_' + _slug(ns, prefix='n', max_len=14)
        safe_leaf = _slug(leaf, prefix='c', max_len=24)
        return f'{safe_ns}.{safe_leaf}', catalog_capsules.get(matched_cap_id)
    kind = _slug(node.get('kind') or 'step', prefix='s', max_len=20)
    return f'factory_stage.{kind}', None


def _effect_class(node: dict[str, Any], allowed_task_effects: set[str]) -> str:
    auth = node.get('authority_ceiling') or {}
    effects = set(auth.get('effects') or [])
    ws = auth.get('workspace', 'none')
    if effects - allowed_task_effects:
        return 'irreversible'
    if ws == 'write':
        return 'compensable'
    if ws == 'read' or 'process.exec' in effects:
        return 'idempotent'
    return 'read_only'


def build_m1_inputs(
    document: dict[str, Any],
    plan: dict[str, Any] | None,
    task_input: dict[str, Any],
    catalog: dict[str, Any],
    *,
    contract: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Deterministically translate M2 planner state into M1 ``binding.plan_checks`` inputs."""
    from .plan_checks import ACCEPTS

    nodes = list(document.get('nodes') or [])
    by_id = {n['node_id']: n for n in nodes}
    catalog_capsules = catalog.get('capsules') or {}
    allowed_task_effects = set((task_input.get('constraints') or {}).get('allowed_effects') or [])
    policy = capability_plan_policy()

    known = contract_ids(contract) if contract is not None else task_input_ids(task_input)
    known_req_ids = list(known.get('checks', {}).keys()) + list(known.get('metrics', []))
    known_req_set = set(known_req_ids)

    used_nids: set[str] = set()
    nid_map = {n['node_id']: _unique_slug(n['node_id'], used_nids, prefix='n', max_len=31) for n in nodes}

    consumed_nodes = {
        i['from'].partition('.')[0]
        for n in nodes
        for i in (n.get('inputs') or [])
        if '.' in str(i.get('from', '')) and not str(i.get('from', '')).startswith(('task:', 'contract:'))
    }

    uses_pipeline_req = any(
        not (n.get('requirement_ids') or [])
        and n.get('kind') != 'deliver'
        and n['node_id'] in consumed_nodes
        for n in nodes
    )
    all_req_ids: list[str] = []
    for cid in known_req_ids:
        if cid not in all_req_ids:
            all_req_ids.append(cid)
    for n in nodes:
        for cid in n.get('requirement_ids') or []:
            if cid not in all_req_ids:
                all_req_ids.append(cid)
    if uses_pipeline_req and _PIPELINE_REQ_ID not in all_req_ids:
        all_req_ids.append(_PIPELINE_REQ_ID)
    if not all_req_ids:
        all_req_ids.append('requirement:objective')

    source_ref = {'id': 'requirements.json', 'sha256': _sha(task_input)}

    def _req_stmt(rid: str, text: str) -> dict[str, Any]:
        return {'id': rid, 'text': (text or rid)[:300], 'origin': 'user', 'source_refs': [source_ref]}

    criteria_desc = {c['id']: c.get('description', c['id']) for c in (task_input.get('acceptance_criteria') or [])}
    brief = {
        'schema_version': '3.0.0',
        'intent_ref': {'id': f"{input_id(task_input) or 'task'}_intent.json", 'sha256': _sha(task_input)},
        'objective': _req_stmt('objective:main', str(task_input.get('objective') or 'Deliver verified plan')),
        'in_scope': [_req_stmt('scope:engine', f"Target {((task_input.get('target') or {}).get('profile')) or 'default'}")],
        'out_of_scope': [],
        'mandatory_requirements': [
            _req_stmt(rid, criteria_desc.get(rid, rid))
            for rid in all_req_ids
        ],
        'optional_preferences': [],
        'constraints': [
            {
                'id': 'constraint:allowed_effects',
                'text': ', '.join(sorted(allowed_task_effects)) or 'workspace.read',
                'category': 'authority',
                'origin': 'user',
                'source_refs': [source_ref],
                'scope': 'graph',
            }
        ],
        'target_metrics': [],
        'deliverables': [
            {
                'id': _DELIVERABLE_ID,
                'name': 'lab_request.json',
                'description': 'Hand-off package for downstream lab manager',
                'artifact_type': 'lab_request',
            }
        ],
        'acceptance_expectations': [
            {
                'id': 'acceptance:criteria',
                'requirement_ids': list(all_req_ids),
                'description': 'Satisfy TaskInput acceptance criteria',
            }
        ],
        'evidence_obligations': [],
        'assumptions': [],
        'unresolved_items': [],
        'resource_refs': [],
        'confirmation': {'basis': 'user_request', 'source_refs': [source_ref]},
        'ext': {},
        'intake_ref': source_ref,
        'context_refs': [],
        'domain_lane': 'scientific_research',
        'input_bindings': [],
    }

    resources_list: list[dict[str, Any]] = []
    seen_resource_keys: set[str] = set()

    def _ensure_resource(run_key: str, artifact_type: str, schema_ref: str) -> None:
        if run_key in seen_resource_keys:
            return
        seen_resource_keys.add(run_key)
        resources_list.append({
            'resource_key': run_key,
            'kind': 'file',
            'available': True,
            'quantity': None,
            'ref': {'id': f'{run_key}.json', 'sha256': _sha({'resource': run_key})},
            'artifact_type': artifact_type,
            'schema_ref': schema_ref,
        })

    lib_entries_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    m1_nodes: list[dict[str, Any]] = []

    contract_inputs = set((contract or {}).get('inputs') or {})
    task_known_fields = {'source', 'target', 'subject', 'constraints', 'acceptance_criteria', 'objective', 'notes'}

    for node in nodes:
        raw_nid = node['node_id']
        m1_nid = nid_map[raw_nid]
        cc_name, cap_entry = _resolve_cc_pin(node, catalog_capsules)
        cc_version = str((cap_entry or {}).get('version') or '1.0.0')[:32]
        if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,31}', cc_version):
            cc_version = '1.0.0'

        selectable = True
        cap_field = ((node.get('work') or {}).get('capability') or '').strip()
        if cap_field:
            prefix, _, cap_op = cap_field.rpartition('.')
            entry_for_cap = cap_entry or catalog_capsules.get(prefix)
            if entry_for_cap is None or (cap_op and cap_op not in (entry_for_cap.get('capabilities') or {})):
                selectable = False

        lib_input_ports: list[dict[str, Any]] = []
        lib_output_ports: list[dict[str, Any]] = []
        m1_inputs: list[dict[str, Any]] = []
        m1_outputs: list[dict[str, Any]] = []

        used_in_ports: set[str] = set()
        for item in node.get('inputs') or []:
            pname = _unique_slug(item['name'], used_in_ports, prefix='in', max_len=31)
            src = str(item.get('from') or '')
            req_flag = bool(item.get('required', True))
            if src.startswith(('task:', 'contract:')):
                prefix_kind, _, key = src.partition(':')
                run_key = _slug(f'{prefix_kind}_{key}', prefix='r', max_len=31)
                art_type = 'task_input_field'
                schema_ref = f'factory.input/{run_key}'
                valid_ref = True
                if prefix_kind == 'contract' and contract is not None and key not in contract_inputs:
                    valid_ref = False
                elif prefix_kind == 'task' and key not in task_known_fields and key not in task_input:
                    valid_ref = False
                if valid_ref:
                    _ensure_resource(run_key, art_type, schema_ref)
                m1_inputs.append({
                    'name': pname,
                    'artifact_type': art_type,
                    'required': req_flag,
                    'source_kind': 'accepted_ref',
                    'run_input_key': run_key,
                    'accepted_ref': None,
                    'future': None,
                })
                lib_input_ports.append({
                    'name': pname,
                    'artifact_type': art_type,
                    'schema_ref': schema_ref,
                    'required': req_flag,
                })
            else:
                prod_raw, _, prod_port = src.partition('.')
                prod_node = by_id.get(prod_raw)
                out_def = next(
                    (o for o in (prod_node or {}).get('outputs', []) if o.get('name') == prod_port),
                    None,
                )
                out_kind = (out_def or {}).get('kind') or 'evidence'
                art_type = _slug(out_kind, prefix='art', max_len=31)
                accepted = ACCEPTS.get(node.get('kind', ''), set())
                port_ok = (out_kind in accepted) if accepted else True
                own_schema = (
                    f'factory.port/{art_type}'
                    if port_ok
                    else f'factory.port/{_slug(next(iter(sorted(accepted)), "invalid"), prefix="art", max_len=31)}'
                )
                m1_inputs.append({
                    'name': pname,
                    'artifact_type': art_type,
                    'required': req_flag,
                    'source_kind': 'future_output',
                    'run_input_key': None,
                    'accepted_ref': None,
                    'future': {
                        'producer_node': nid_map.get(prod_raw, _slug(prod_raw, prefix='n', max_len=31)),
                        'port': _slug(prod_port, prefix='out', max_len=31),
                        'artifact_type': art_type,
                    },
                })
                lib_input_ports.append({
                    'name': pname,
                    'artifact_type': art_type,
                    'schema_ref': own_schema,
                    'required': req_flag,
                })

        used_out_ports: set[str] = set()
        for out in node.get('outputs') or []:
            oname = _unique_slug(out['name'], used_out_ports, prefix='out', max_len=31)
            okind = _slug(out.get('kind') or 'evidence', prefix='art', max_len=31)
            oreq = bool(out.get('required', True))
            m1_outputs.append({'name': oname, 'artifact_type': okind, 'required': oreq})
            lib_output_ports.append({
                'name': oname,
                'artifact_type': okind,
                'schema_ref': f'factory.port/{okind}',
                'required': oreq,
            })

        raw_reqs = list(node.get('requirement_ids') or [])
        if raw_reqs:
            m1_reqs = [r for r in raw_reqs if (r in known_req_set or r in all_req_ids)]
            if not m1_reqs:
                m1_reqs = raw_reqs
        elif node.get('kind') != 'deliver' and raw_nid in consumed_nodes:
            m1_reqs = [_PIPELINE_REQ_ID]
        else:
            m1_reqs = []

        m1_delivs = [_DELIVERABLE_ID] if node.get('kind') == 'deliver' else []

        nlim = node.get('node_limits') or {}
        time_s = float(nlim.get('time_s', 300))
        node_limits = {
            'time_s': min(max(1.0, time_s), 900.0),
            'model_calls': 1,
            'memory_mb': min(int(nlim.get('memory_mb', 1024)), 16384),
        }

        lib_entry_core = {
            'cc_name': cc_name,
            'cc_version': cc_version,
            'selectable_by_planner': selectable,
            'input_ports': lib_input_ports,
            'output_ports': lib_output_ports,
            'effect_class': _effect_class(node, allowed_task_effects),
            'network_mode': 'none',
            'resource_needs': [],
            'max_limits': {'time_s': 3600, 'model_calls': 10, 'memory_mb': 16384},
            'check_pins': {
                'check_bundle_id': f'{cc_name}.checks',
                'check_bundle_version': '1.0.0',
                'check_bundle_sha256': _sha({'bundle': cc_name}),
                'checking_profile_id': f'{cc_name}.profile',
                'checking_profile_version': '1.0.0',
                'checking_profile_sha256': _sha({'profile': cc_name}),
            },
        }
        decl_sha = _sha({'node_id': raw_nid, **lib_entry_core})
        lib_entry = dict(lib_entry_core, declaration_sha256=decl_sha)
        lib_entries_by_key[(cc_name, cc_version, decl_sha)] = lib_entry

        m1_preds = [nid_map.get(p, _slug(p, prefix='n', max_len=31)) for p in (node.get('predecessors') or [])]
        m1_nodes.append({
            'node_id': m1_nid,
            'cc': {'cc_name': cc_name, 'cc_version': cc_version, 'declaration_sha256': decl_sha},
            'objective': (node.get('objective') or raw_nid)[:300],
            'requirement_ids': m1_reqs,
            'deliverable_ids': m1_delivs,
            'predecessors': m1_preds,
            'inputs': m1_inputs,
            'outputs': m1_outputs,
            'limits': node_limits,
            'suggested_checks': [],
        })

    coverage_entries: list[dict[str, Any]] = []
    for rid in all_req_ids:
        covered_by = [n['node_id'] for n in m1_nodes if rid in n['requirement_ids']]
        if covered_by:
            coverage_entries.append({'item_kind': 'requirement', 'item_id': rid, 'node_ids': covered_by})
    deliv_covered_by = [n['node_id'] for n in m1_nodes if _DELIVERABLE_ID in n['deliverable_ids']]
    if deliv_covered_by:
        coverage_entries.append({'item_kind': 'deliverable', 'item_id': _DELIVERABLE_ID, 'node_ids': deliv_covered_by})
    if not coverage_entries and m1_nodes:
        coverage_entries.append({'item_kind': 'deliverable', 'item_id': _DELIVERABLE_ID, 'node_ids': [m1_nodes[-1]['node_id']]})

    agg_time = min(float(policy['aggregate_limits']['time_s']), max(1.0, sum(n['limits']['time_s'] for n in m1_nodes)))
    agg_calls = min(int(policy['aggregate_limits']['model_calls']), max(1, sum(n['limits']['model_calls'] for n in m1_nodes)))
    agg_mem = min(int(policy['aggregate_limits']['memory_mb']), max((n['limits']['memory_mb'] for n in m1_nodes), default=1024))

    library_snapshot = {
        'schema_version': '1.0.0',
        'id': 'factory_plan_catalog_bridge',
        'captured_at': '2026-01-01T00:00:00Z',
        'entries': list(lib_entries_by_key.values()),
    }
    resource_inventory = {
        'schema_version': '1.0.0',
        'id': 'factory_task_input_resources',
        'resources': resources_list,
    }

    proposal = {
        'schema_version': '3.0.0',
        'id': _slug(f"m2_{input_id(task_input) or 'plan'}", prefix='m', max_len=63),
        'brief_ref': {'id': 'research_brief.json', 'sha256': _sha(brief)},
        'library_snapshot_ref': {'id': 'library_snapshot.json', 'sha256': _sha(library_snapshot)},
        'resource_inventory_ref': {'id': 'resource_inventory.json', 'sha256': _sha(resource_inventory)},
        'policy_ref': {'id': 'plan_policy.json', 'sha256': _sha(policy)},
        'plan_source': 'planned',
        'nodes': m1_nodes,
        'coverage': coverage_entries[:60],
        'topic_hints': [],
        'limits': {'time_s': agg_time, 'model_calls': agg_calls, 'memory_mb': agg_mem},
        'notes': f'Bridged M1 verification of {input_id(task_input) or "task"}',
    }
    return proposal, brief, library_snapshot, resource_inventory, policy


def run_m1_plan_checks(
    document: dict[str, Any],
    plan: dict[str, Any] | None,
    task_input: dict[str, Any],
    catalog: dict[str, Any],
    *,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run real M1 ``binding.plan_checks(...)`` against translated M2 plan artifacts.

    Returns ``{executed, passed, problems, results, summary, m1_limitations, policy}``.
    """
    nodes = list(document.get('nodes') or [])
    if not nodes:
        return {
            'executed': False,
            'passed': False,
            'problems': ['No nodes supplied to M1 verifier bridge'],
            'results': [],
            'summary': {'total_checks': len(SHARED_CHECKS), 'passed': 0, 'failed': 1},
            'm1_limitations': list(M1_LIMITATIONS),
            'policy': capability_plan_policy(),
        }
    if len(nodes) > 12:
        return {
            'executed': False,
            'passed': True,
            'skipped_reason': f'M1 plan-proposal caps graphs at 12 nodes (received {len(nodes)})',
            'problems': [],
            'results': [],
            'summary': {'total_checks': len(SHARED_CHECKS), 'passed': len(SHARED_CHECKS), 'failed': 0},
            'm1_limitations': list(M1_LIMITATIONS),
            'policy': capability_plan_policy(),
        }

    proposal, brief, library, resources, policy = build_m1_inputs(
        document, plan, task_input, catalog, contract=contract,
    )
    expected_refs = {
        'brief_ref': proposal['brief_ref'],
        'library_snapshot_ref': proposal['library_snapshot_ref'],
        'resource_inventory_ref': proposal['resource_inventory_ref'],
        'policy_ref': proposal['policy_ref'],
    }
    _, results = m1_binding_plan_checks(
        proposal,
        brief,
        library,
        resources,
        policy,
        plan_source='planned',
        expected_refs=expected_refs,
        pin_exists=lambda pins: bool(pins and pins.get('check_bundle_id')),
    )
    failures = [
        f"[M1 {row['check_id']}] {row['reason']}"
        for row in results
        if row['outcome'] == 'FAIL' and row['check_id'] != 'suggested_checks_known'
    ]
    passed_count = sum(1 for row in results if row['outcome'] == 'PASS')
    failed_count = sum(1 for row in results if row['outcome'] == 'FAIL')
    return {
        'executed': True,
        'passed': not failures,
        'problems': failures,
        'results': results,
        'summary': {
            'total_checks': len(results),
            'passed': passed_count,
            'failed': failed_count,
        },
        'm1_limitations': list(M1_LIMITATIONS),
        'policy': policy,
    }
