"""Static checks a planned TaskGraph must pass before TLC and downstream hand-off.

The structural rules enforced at ``jiuwenswarm-factory init`` run first
(``node_contract.problems``, ``planner.check_plan``). The checks here add semantic
safety: every acceptance criterion and target is covered, every capsule and verifier
exists, authority stays within TaskInput grants, concurrent code changes are merged
before building, port types match, and no step serves nothing.
"""
from __future__ import annotations

WORKSPACE_EFFECTS = {'none': set(), 'read': {'workspace.read'}, 'write': {'workspace.read', 'workspace.write'}}
SHIPPED_KINDS = {'source_bundle', 'image'}


def _descendants(nodes):
    children = {key: [] for key in nodes}
    for key, node in nodes.items():
        for parent in node.get('predecessors', []):
            if parent in children:
                children[parent].append(key)
    result = {}
    for key in nodes:
        seen, pending = set(), list(children[key])
        while pending:
            child = pending.pop()
            if child not in seen:
                seen.add(child)
                pending.extend(children[child])
        result[key] = seen
    return result


def _has_real_artifact(owners):
    """True when at least one step produces a required code diff or capsule-verified evidence artifact."""
    for node in owners:
        verified = {v['output'] for v in node['verifiers'] if v.get('verifier')}
        for output in node['outputs']:
            if not output.get('required', True):
                continue
            if output['kind'] == 'diff' or (output['kind'] == 'evidence' and output['name'] in verified):
                return True
    return False


def coverage(nodes, known):
    """Every acceptance criterion / metric is owned; the solution produces artifacts and ships one final build."""
    found = []
    delivers = [n for n in nodes.values() if n['kind'] == 'deliver']
    deliver_ids = set(delivers[0].get('requirement_ids', [])) if len(delivers) == 1 else set()
    all_owned = {rid for n in nodes.values() for rid in n.get('requirement_ids', [])}

    if 'all_criteria' in known:
        # Single-solution TaskInput mode
        for cid in known['all_criteria']:
            if cid not in deliver_ids:
                found.append(f'criterion {cid}: the deliver node must list it, so the lab verifies it')
        for cid in known['checks']:
            non_deliver = [n for n in nodes.values() if n['kind'] != 'deliver' and cid in n.get('requirement_ids', [])]
            if not non_deliver and cid not in deliver_ids:
                found.append(f'criterion {cid}: an execution step or deliver node must own it')
        producers = [n for n in nodes.values() if n['kind'] != 'deliver']
        if not _has_real_artifact(producers):
            found.append('no step produces a required code change (diff) or verified artifact')
        shippers = [n for n in nodes.values() if any(o['kind'] in SHIPPED_KINDS and o.get('required', True) for o in n['outputs'])]
        if not shippers:
            found.append('no build step ships a final source_bundle or image for delivery')
        return found

    # Legacy multi-arm contract mode (used by verify-plan CLI on format-2 contracts)
    for requirement in [*known['arms'], *known['metrics']]:
        if requirement not in deliver_ids:
            found.append(f'requirement {requirement}: the deliver node must list it, so the lab runs it')
    for check in known['checks']:
        if check not in all_owned:
            found.append(f'requirement {check}: the deliver node or a factory check step must list it')
    for arm in known.get('realizable_arms', known['built_arms']):
        owners = [n for n in nodes.values() if arm in n.get('requirement_ids', [])]
        if not _has_real_artifact(owners):
            found.append(f'arm {arm}: no step that lists it produces a required code change or verified artifact')
        if not any(o['kind'] in SHIPPED_KINDS for n in owners for o in n['outputs']):
            found.append(f'arm {arm}: no step that lists it ships a source_bundle or image for the lab')
    return found


def hints(nodes, task_input):
    found = []
    hint_map = task_input.get('hints') or {}
    verifiers = {v.get('verifier') for n in nodes.values() for v in n['verifiers'] if v.get('verifier')}
    for capsule in hint_map.get('must_include') or []:
        if not any(name.startswith(capsule + '.') for name in verifiers):
            found.append(f'hints/must_include: {capsule} is required, so a step must be verified by {capsule}')
    excludes = set(hint_map.get('excludes') or [])
    if excludes:
        for key, node in nodes.items():
            work = node.get('work') or {}
            cap = (work.get('capability') or '').rpartition('.')[0]
            used = set(work.get('helpful_ccs') or []) | ({cap} if cap else set())
            used |= {v['verifier'].rpartition('.')[0] for v in node['verifiers'] if v.get('verifier')}
            bad = sorted(used & excludes)
            if bad:
                found.append(f'{key}: excluded capsule(s) {bad} cannot be used')
    for arm, capsule in (hint_map.get('realizes') or {}).items():
        arm_verifiers = {v.get('verifier') for n in nodes.values() if arm in n.get('requirement_ids', [])
                         for v in n['verifiers'] if v.get('verifier')}
        if not any(name.startswith(capsule + '.') for name in arm_verifiers):
            found.append(f'arm {arm}: hints say {capsule} builds it; a step listing {arm} must be verified by {capsule}')
    return found


def catalog_closure(nodes, catalog):
    from .plan_catalog import capability, is_verifier
    found = []
    for key, node in nodes.items():
        work = node.get('work') or {}
        if work.get('capability') and capability(catalog, work['capability']) is None:
            found.append(f'{key}/work/capability: {work["capability"]} is not a capability in the capsule catalog')
        for capsule in work.get('helpful_ccs', []):
            if capsule not in catalog['capsules']:
                found.append(f'{key}/work/helpful_ccs: no capsule {capsule} in the catalog')
        for verifier in node['verifiers']:
            name = verifier.get('verifier')
            if name and not is_verifier(catalog, name):
                found.append(f'{key}/verifiers/{verifier["output"]}: {name} is not a verify capability in the catalog')
    return found


def authority(nodes, task_input, catalog):
    from .plan_catalog import capability
    found = []
    allowed = set(task_input['constraints']['allowed_effects'])
    for key, node in nodes.items():
        ceiling = node.get('authority_ceiling')
        if not ceiling or 'effects' not in ceiling or 'workspace' not in ceiling:
            found.append(f'{key}/authority_ceiling: state both effects and workspace, the least the step needs')
            continue
        effects = set(ceiling['effects'])
        if effects - allowed:
            found.append(f'{key}/authority_ceiling: {sorted(effects - allowed)} exceed the task\'s allowed effects {sorted(allowed)}')
        workspace_effects = {e for e in effects if e.startswith('workspace.')}
        if workspace_effects - WORKSPACE_EFFECTS[ceiling['workspace']]:
            found.append(f'{key}/authority_ceiling: effects {sorted(workspace_effects)} contradict workspace {ceiling["workspace"]}')
        if any(o['kind'] == 'diff' for o in node['outputs']) and ceiling['workspace'] != 'write':
            found.append(f'{key}/authority_ceiling: a step that produces a diff needs workspace write')
        cap = (node.get('work') or {}).get('capability')
        needed = set((capability(catalog, cap) or {}).get('changes', [])) if cap else set()
        if needed - effects:
            found.append(f'{key}/work/capability: {cap} changes {sorted(needed - effects)}, beyond the step\'s ceiling')
    return found


def _diff_lineage(nodes):
    kinds = {k: {o['name']: o['kind'] for o in n['outputs']} for k, n in nodes.items()}
    memo = {}

    def lineage(key):
        if key not in memo:
            memo[key] = set()
            for item in nodes[key].get('inputs', []):
                producer, _, port = item['from'].partition('.')
                if producer in nodes and kinds[producer].get(port) == 'diff':
                    memo[key] |= {producer} | lineage(producer)
        return memo[key]
    return {key: lineage(key) for key in nodes}


def join_before_build(nodes):
    """Concurrent code changes are merged, directly or in stages, before anything is built."""
    found = []
    below = _descendants(nodes)
    lineage = _diff_lineage(nodes)
    diffs = sorted(k for k, n in nodes.items() if any(o['kind'] == 'diff' for o in n['outputs']))
    sinks = [k for k, n in nodes.items()
             if n['kind'] == 'build' and any(o['kind'] in SHIPPED_KINDS for o in n['outputs'])] \
        or [k for k, n in nodes.items() if n['kind'] == 'deliver']
    for index, u in enumerate(diffs):
        for v in diffs[index + 1:]:
            if v in below[u] or u in below[v]:
                continue
            joined = any(n['kind'] == 'integrate' and {u, v} <= lineage[k] and all(sink in below[k] for sink in sinks)
                         for k, n in nodes.items())
            if not joined:
                found.append(f'{u} and {v} change code independently; add an integrate step that takes both '
                             f'changes as inputs and precedes {", ".join(sinks)}')
    return found


ACCEPTS = {'inspect': {'evidence'}, 'investigate': {'evidence', 'diff'}, 'decide': {'evidence'},
           'integrate': {'evidence', 'diff', 'source_bundle'}, 'build': {'diff', 'evidence', 'source_bundle'},
           'measure': {'image', 'source_bundle', 'evidence'}, 'tune': {'evidence', 'diff'},
           'accept': {'evidence'}, 'report': {'evidence'}, 'deliver': {'source_bundle', 'image'}}


def port_types(nodes):
    """An input carries the kind of the output it comes from; the consuming step must accept it."""
    found = []
    for key, node in nodes.items():
        for item in node.get('inputs', []):
            producer, _, port = item['from'].partition('.')
            if producer not in nodes:
                continue
            kind = next((o['kind'] for o in nodes[producer]['outputs'] if o['name'] == port), None)
            accepted = ACCEPTS.get(node['kind'])
            if kind and accepted is not None and kind not in accepted:
                found.append(f'{key}/inputs/{item["name"]}: a {node["kind"]} step does not consume {kind} '
                             f'(it takes {", ".join(sorted(accepted))})')
    return found


def purpose(nodes):
    found = []
    consumed = {i['from'].partition('.')[0] for n in nodes.values() for i in n.get('inputs', [])}
    for key, node in nodes.items():
        if node['kind'] != 'deliver' and not node.get('requirement_ids') and key not in consumed:
            found.append(f'{key}: serves no requirement and no later step uses its outputs; remove it or connect it')
    return found


def budget(nodes, task_input):
    """Warnings only: limits are advice to the scheduler, the task budget enforces totals."""
    warnings = []
    max_turns = task_input['constraints']['budget']['max_turns']
    missing = [k for k, n in nodes.items() if 'turns' not in (n.get('node_limits') or {})]
    if missing:
        warnings.append(f'no turn limit on {", ".join(sorted(missing))}')
    total = sum((n.get('node_limits') or {}).get('turns', 0) for n in nodes.values())
    if total > max_turns:
        warnings.append(f'node turn limits add up to {total}, above the task budget of {max_turns} turns')
    if all('time_s' in (n.get('node_limits') or {}) for n in nodes.values()):
        longest = {}
        from .node_contract import order
        for key in order(list(nodes.values())):
            node = nodes[key]
            longest[key] = node['node_limits']['time_s'] + max((longest[p] for p in node.get('predecessors', [])), default=0)
        if max(longest.values(), default=0) > task_input['constraints']['budget']['wall_clock_s']:
            warnings.append('the longest chain of node time limits exceeds the task wall clock budget')
    return warnings


def run_detailed(document, plan, task_input, catalog, contract=None):
    """Run legacy M1 ``binding.plan_checks`` (bridged) + M2 8-rule checks, returning full audit details."""
    from .m1_verifier_bridge import run_m1_plan_checks
    from .node_contract import problems as structure
    from .planner import check_plan
    from .requirements import contract_ids, contract_of, ids
    check_contract = contract or contract_of(task_input)
    found = structure(document, check_contract)
    if found:
        return dict(problems=found, warnings=[], m1_bridge=None)
    found += check_plan(plan, document)
    m1_bridge = run_m1_plan_checks(document, plan, task_input, catalog, contract=check_contract)
    found += m1_bridge['problems']
    nodes = {n['node_id']: n for n in document['nodes']}
    known = contract_ids(contract) if contract is not None else ids(task_input)
    found += coverage(nodes, known)
    found += hints(nodes, task_input)
    found += catalog_closure(nodes, catalog)
    found += authority(nodes, task_input, catalog)
    found += join_before_build(nodes)
    found += port_types(nodes)
    found += purpose(nodes)
    warns = budget(nodes, task_input)
    return dict(problems=found, warnings=warns, m1_bridge=m1_bridge)


def run(document, plan, task_input, catalog, contract=None):
    """(problems, warnings). Runs bridged M1 ``binding.plan_checks`` plus M2 checks before TLC."""
    result = run_detailed(document, plan, task_input, catalog, contract=contract)
    return result['problems'], result['warnings']


def _signature(node):
    return (node['kind'], frozenset(v.get('verifier') for v in node['verifiers'] if v.get('verifier')))


def compare(reference, planned):
    """How a planned graph differs from a reference graph, node by node."""
    ref = {n['node_id']: n for n in reference['nodes']}
    new = {n['node_id']: n for n in planned['nodes']}
    mapping = {key: key for key in new if key in ref and _signature(new[key]) == _signature(ref[key])}
    for key, node in new.items():
        if key in mapping:
            continue
        free = [r for r in ref if r not in mapping.values() and _signature(ref[r]) == _signature(node)]
        if free:
            best = max(free, key=lambda r: len(set(ref[r].get('requirement_ids', [])) & set(node.get('requirement_ids', []))))
            mapping[key] = best
    rows = []
    for key, rkey in sorted(mapping.items(), key=lambda item: list(ref).index(item[1])):
        a, b = ref[rkey], new[key]
        differences = []
        mapped = sorted(mapping.get(p, '?' + p) for p in b.get('predecessors', []))
        if mapped != sorted(a.get('predecessors', [])):
            differences.append(dict(field='predecessors', reference=sorted(a.get('predecessors', [])), planned=mapped))
        for field, value in (('outputs', lambda n: sorted(f"{o['name']}:{o['kind']}" for o in n['outputs'])),
                             ('requirement_ids', lambda n: sorted(n.get('requirement_ids', []))),
                             ('verifiers', lambda n: sorted(f"{v['output']}:{v.get('verifier') or ''}:{bool(v.get('review'))}" for v in n['verifiers'])),
                             ('node_limits', lambda n: n.get('node_limits', {})),
                             ('authority_ceiling', lambda n: {k: sorted(v) if isinstance(v, list) else v
                                                              for k, v in (n.get('authority_ceiling') or {}).items()})):
            if value(a) != value(b):
                differences.append(dict(field=field, reference=value(a), planned=value(b)))
        rows.append(dict(reference=rkey, planned=key, kind=b['kind'], differences=differences))
    missing = [k for k in ref if k not in mapping.values()]
    extra = [k for k in new if k not in mapping]
    structural = {'predecessors', 'outputs', 'verifiers', 'requirement_ids'}
    return dict(rows=rows, missing=missing, extra=extra,
                structurally_equivalent=not missing and not extra and not any(
                    d['field'] in structural for r in rows for d in r['differences']))
