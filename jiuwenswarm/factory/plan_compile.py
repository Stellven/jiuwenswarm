"""Plan IR + CC Library -> node contracts + plan: autonomous step DAG compiler.

The model inspects the full CC Library (``plan_catalog.prompt_view``) and host selection
context (``plan_select.context``), chooses capsules, and designs its own TaskGraph ``steps``
(step id, kind, objective, depends_on, bound CCs, optional limits/criteria/outputs).
This module validates those choices and compiles them deterministically into a
single-solution ``factory.node-contracts/1`` document and ``factory.plan/1`` schedule,
ready for M1+M2 static checks and internal 2-pass TLC formal verification.
"""
from __future__ import annotations

import re

from . import plan_catalog
from . import plan_checks
from . import plan_ir
from . import tla_graph
from .plan_select import interference, merge_options, unit_components

PLANNER = 'factory.ai_planner'
CIO = 'captured_input_and_output'
DEFAULT_LIMITS = {
    'inspect': {'turns': 10},
    'investigate': {'turns': 10},
    'preflight': {'turns': 10},
    'integrate': {'turns': 40, 'build_attempts': 0},
    'merge': {'turns': 20},
    'build': {'turns': 15, 'build_attempts': 3},
    'measure': {'turns': 15},
    'decide': {'turns': 10},
    'tune': {'turns': 20},
    'accept': {'turns': 10},
    'report': {'turns': 10},
    'deliver': {'turns': 10},
}
EVIDENCE = {
    'inspect': [CIO],
    'investigate': [CIO, 'semantic_assessment'],
    'preflight': [CIO, 'semantic_assessment'],
    'integrate': [CIO, 'mandatory_checks', 'semantic_assessment'],
    'merge': [CIO, 'semantic_assessment'],
    'build': [CIO, 'invocation_observation'],
    'measure': [CIO, 'invocation_observation'],
    'decide': [CIO, 'semantic_assessment'],
    'tune': [CIO, 'mandatory_checks'],
    'accept': [CIO, 'semantic_assessment'],
    'report': [CIO],
    'deliver': [CIO, 'invocation_observation'],
}
HELPFUL = {
    'inspect': ['factory.engine_inspector', 'factory.source_workbench'],
    'merge': ['factory.integration_skill', 'factory.source_workbench'],
    'build': ['factory.lab_manager', 'factory.builder'],
    'measure': ['factory.lab_manager'],
    'deliver': ['factory.lab_manager'],
}
WORKSPACE = {
    'inspect': 'read',
    'investigate': 'read',
    'preflight': 'read',
    'integrate': 'write',
    'merge': 'write',
    'build': 'read',
    'measure': 'read',
    'decide': 'read',
    'tune': 'write',
    'accept': 'read',
    'report': 'read',
    'deliver': 'none',
}
MAX_CRITERIA = 12


class CompileError(ValueError):
    def __init__(self, problems):
        super().__init__('; '.join(problems))
        self.problems = problems


def _clip(text):
    text = ' '.join(str(text).split())
    return text if len(text) <= 600 else text[:597] + '...'


def _slug_id(raw: str) -> str:
    cleaned = re.sub(r'[^a-z0-9_]', '_', str(raw or '').lower())[:32].strip('_')
    return cleaned if cleaned and cleaned[0].isalpha() else ('s_' + (cleaned or 'out'))[:32]


def _unique_in_name(candidate: str, seen: set[str], producer_id: str) -> str:
    name = _slug_id(candidate)
    if name not in seen:
        seen.add(name)
        return name
    prefixed = _slug_id(f'{producer_id}_{name}')
    idx = 2
    cur = prefixed
    while cur in seen:
        suffix = f'_{idx}'
        cur = prefixed[:32 - len(suffix)] + suffix
        idx += 1
    seen.add(cur)
    return cur


def _has_tool_compiler(step: dict, capsules: dict) -> str | None:
    for cid in step.get('capsules') or []:
        cap = capsules.get(cid)
        if cap and not cap['builder'] and 'verify_pack' in cap['verifiers']:
            return cid
    return None


def _is_preflight_step(step: dict, unit_caps: set[str]) -> bool:
    if step['kind'] not in {'inspect', 'investigate'}:
        return False
    return bool(step['id'].startswith('preflight_') or (step.get('depends_on') and (unit_caps & set(step.get('capsules') or []))))


def _expand_merge_steps(steps: list[dict], ir: dict, units: dict, cap_to_unit: dict[str, str]) -> list[dict]:
    """If a single `combine` merge step was declared with option M2/M3, expand it into staged sub-merges."""
    diffs = plan_ir.diff_units(units)
    merge_steps = [s for s in steps if s['kind'] == 'merge']
    if len(diffs) < 2 or len(merge_steps) != 1 or merge_steps[0]['id'] != 'combine':
        return steps
    option = (ir.get('merge') or {}).get('option', 'M1')
    m_opts = merge_options(diffs, interference(unit_components({u: units[u] for u in diffs})))
    stages = (m_opts.get(option) or {}).get('stages') or []
    if len(stages) <= 1:
        return steps

    unit_to_integrate: dict[str, str] = {}
    for s in steps:
        if s['kind'] == 'integrate':
            for cid in s.get('capsules') or []:
                if cid in cap_to_unit and cap_to_unit[cid] in diffs:
                    unit_to_integrate[cap_to_unit[cid]] = s['id']
    if len(unit_to_integrate) < 2:
        return steps

    combine_step = merge_steps[0]
    existing_ids = {s['id'] for s in steps}
    expanded: list[dict] = []
    for mst in stages:
        mid = mst['id']
        if mid != 'combine' and mid in existing_ids:
            return steps
        deps = [unit_to_integrate.get(m, m) for m in mst['members']]
        is_final = mid == 'combine'
        expanded.append(dict(
            combine_step if is_final else {},
            id=mid,
            kind='merge',
            objective=combine_step['objective'] if is_final else f'Intermediate staged merge for {", ".join(mst["members"])}.',
            depends_on=deps,
            capsules=list(combine_step.get('capsules') or ['factory.integration_skill', 'factory.source_workbench']),
        ))
    out: list[dict] = []
    for s in steps:
        if s is combine_step:
            out.extend(expanded)
        else:
            out.append(s)
    return out


def _toposort_with_priority(steps: list[dict], priority: list[list[str]], cap_to_unit: dict[str, str], capsules: dict) -> tuple[list[dict], dict[str, list[str]]]:
    unit_exec: dict[str, str] = {}
    for s in steps:
        if s['kind'] in {'integrate', 'build'}:
            for cid in s.get('capsules') or []:
                u = cap_to_unit.get(cid)
                if u and (capsules[cid]['builder'] or _has_tool_compiler(s, capsules)):
                    unit_exec.setdefault(u, s['id'])

    eff_deps = {s['id']: list(s.get('depends_on') or []) for s in steps}
    for before_u, after_u in priority:
        sb, sa = unit_exec.get(before_u), unit_exec.get(after_u)
        if sb and sa and sb != sa and sb not in eff_deps[sa]:
            eff_deps[sa].append(sb)

    by_id = {s['id']: s for s in steps}
    pending = {s['id']: set(eff_deps[s['id']]) for s in steps}
    done, ordered = set(), []
    while pending:
        ready = [s['id'] for s in steps if s['id'] in pending and pending[s['id']] <= done]
        if not ready:
            raise CompileError(['steps + priority contain a dependency cycle: ' + ', '.join(sorted(pending))])
        for sid in ready:
            ordered.append(by_id[sid])
            done.add(sid)
            del pending[sid]
    return ordered, eff_deps


def compile_plan(ir, selection, task_input, catalog=None):
    """(document, plan, derivation) from autonomous Plan IR steps + selection + TaskInput."""
    catalog = catalog or plan_catalog.load()
    found = plan_ir.problems(ir, selection, catalog=catalog)
    if found:
        raise CompileError(found)
    if 'unrealizable' in ir:
        raise CompileError([f'unrealizable: {ir["unrealizable"]["why"]}'])

    capsules = catalog['capsules']
    units = plan_ir.units_of(ir, selection)
    cap_to_unit = {cid: u for u, spec in units.items() for cid in spec['capsules']}
    unit_caps = set(cap_to_unit)

    raw_steps = _expand_merge_steps(list(ir['steps']), ir, units, cap_to_unit)
    ordered_steps, eff_deps = _toposort_with_priority(raw_steps, list(ir.get('priority') or []), cap_to_unit, capsules)

    risks = {r['capsule']: r['detail'] for r in selection['risks']}
    preflight = {p['unit']: p for p in ir.get('preflight', []) if p['add']}
    allowed = set(task_input['constraints']['allowed_effects'])
    notes = list(task_input.get('notes') or [])
    ac_items = list(task_input['acceptance_criteria'])
    correctness_ac = [c for c in ac_items if c['kind'] == 'correctness']
    metric_ac = [c for c in ac_items if c['kind'] == 'metric']
    constraint_ac = [c for c in ac_items if c['kind'] == 'constraint']
    all_ac_ids = [c['id'] for c in ac_items]
    revision = (selection.get('engine_revision') or '')[:9]
    model_name = (selection.get('subject') or {}).get('model', {}).get('name', 'target model')
    target_profile = (selection.get('target') or {}).get('profile', 'target')
    selected_reasons = {b['capsule']: b['why'] for b in ir['selected_capsules']}

    deliver_deps = {d for s in ordered_steps if s['kind'] == 'deliver' for d in eff_deps[s['id']]}
    final_packaging_builds = {
        s['id'] for s in ordered_steps if s['kind'] == 'build' and not _has_tool_compiler(s, capsules)
    }

    log, nodes, problems = [], [], []

    def derive(node_id, rule, detail):
        log.append(dict(node=node_id, rule=rule, detail=detail))

    derive('steps', 'autonomous_topology', f'{len(ordered_steps)} steps: ' + ' -> '.join(s['id'] for s in ordered_steps))

    def authority(key, step_key, capability=None, ws_override=None):
        effects = {'process.exec'}
        workspace = ws_override or WORKSPACE[step_key]
        effects |= {'workspace.read'} if workspace in {'read', 'write'} else set()
        effects |= {'workspace.write'} if workspace == 'write' else set()
        if capability:
            effects |= set(plan_catalog.capability(catalog, capability)['changes'])
        if effects - allowed:
            problems.append(f'infeasible_authority: step {key} needs {sorted(effects - allowed)}, '
                            f'which the task does not allow')
        derive(key, 'authority', f'{sorted(effects)} from {capability or "its outputs"}; workspace {workspace}')
        return dict(effects=sorted(effects), workspace=workspace)

    def limits(key, step_key, step_limits=None):
        defaults = dict(DEFAULT_LIMITS[step_key])
        values = dict(defaults)
        for src in (step_limits or {}, (ir.get('limits') or {}).get(key) or {}):
            for field, value in src.items():
                if field in defaults and value > defaults[field]:
                    problems.append(f'limits/{key}/{field}: {value} loosens the default {defaults[field]}; limits may only tighten')
                else:
                    values[field] = value
        tightened = bool(step_limits or (ir.get('limits') or {}).get(key))
        derive(key, 'limits', f'{values} (defaults for {step_key}{", tightened by the plan" if tightened else ""})')
        return values

    def node(key, kind, step_key, objective, predecessors, inputs, outputs, verifiers, requirement_ids, helpful,
             capability=None, extra_evidence=(), step_limits=None, step_criteria=None, ws_override=None):
        extra = list(step_criteria or []) + list((ir.get('criteria') or {}).get(key, []))
        if extra and outputs:
            outputs[0]['criteria'] = (outputs[0].get('criteria', []) + [_clip(c) for c in extra])[:MAX_CRITERIA]
        evidence = list(dict.fromkeys(EVIDENCE[step_key] + list(extra_evidence)))
        entry = dict(
            node_id=key, kind=kind, objective=_clip(objective)[:300],
            requirement_ids=sorted(set(requirement_ids)),
            predecessors=list(dict.fromkeys(predecessors)), inputs=inputs, outputs=outputs,
            evidence_obligations=evidence, node_limits=limits(key, step_key, step_limits),
            authority_ceiling=authority(key, step_key, capability, ws_override=ws_override),
            work=dict(helpful_ccs=list(dict.fromkeys(helpful)), **({'capability': capability} if capability else {})),
            verifiers=verifiers, hands_to='',
        )
        if not entry['predecessors']:
            entry.pop('predecessors')
        if not entry['requirement_ids']:
            entry.pop('requirement_ids')
        nodes.append(entry)
        derive(key, 'requirements', f'{entry.get("requirement_ids", [])}')
        return entry

    def _matching_ac(capsule_id, is_pack=False):
        matched = [c for c in correctness_ac if c.get('verifiable_by', '').startswith(capsule_id + '.')]
        if matched:
            return matched
        if is_pack:
            return [c for c in correctness_ac if 'pack' in c['id'] or 'census' in c['id']]
        return [c for c in correctness_ac if not c.get('verifiable_by') and 'pack' not in c['id'] and 'census' not in c['id']]

    node_by_id: dict[str, dict] = {}
    diff_units_covered: dict[str, list[str]] = {}
    pairs_map = {frozenset((p['a'], p['b'])): p for p in interference(unit_components(units, catalog))}
    merge_ids = [s['id'] for s in ordered_steps if s['kind'] == 'merge']
    ancestors: dict[str, set[str]] = {}

    def _pull_inputs(consumer_kind: str, preds: list[str], *, preferred_kinds: tuple[str, ...] | None = None,
                     all_matching: bool = False, skip_ports: set[str] | None = None) -> list[dict]:
        accepted = plan_checks.ACCEPTS[consumer_kind]
        seen: set[str] = set()
        pulled: list[dict] = []
        for pid in preds:
            pnode = node_by_id.get(pid)
            if not pnode:
                continue
            outs = [o for o in pnode.get('outputs', []) if o['kind'] in accepted and o['name'] not in (skip_ports or ())]
            if preferred_kinds:
                ranked = [o for k in preferred_kinds for o in outs if o['kind'] == k]
                outs = ranked or outs
            if not outs:
                continue
            chosen = outs if all_matching else [outs[0]]
            for out in chosen:
                in_name = _unique_in_name(out['name'], seen, pid)
                pulled.append(dict(name=in_name, **{'from': f'{pid}.{out["name"]}'}))
        return pulled

    for step in ordered_steps:
        sid = step['id']
        skind = step['kind']
        preds = list(eff_deps[sid])
        ancestors[sid] = set(preds) | {a for p in preds for a in ancestors.get(p, ())}
        scaps = list(step.get('capsules') or [])
        ws_ovr = step.get('workspace')
        s_lim = step.get('limits')
        s_crit = step.get('criteria')
        raw_outs = step.get('outputs')

        derive(sid, 'step', f'kind={skind}, depends_on={preds}, capsules={scaps}')

        if _is_preflight_step(step, unit_caps):
            matched_units = [cap_to_unit[c] for c in scaps if c in cap_to_unit]
            unit_lbl = matched_units[0] if matched_units else sid
            detail = '; '.join(risks[c] for c in scaps if c in risks) or (preflight.get(unit_lbl) or {}).get('why', step['objective'])
            inputs = _pull_inputs('inspect', preds) or [dict(name='source', **{'from': 'task:source'})]
            outputs = [dict(
                name='applicability', kind='evidence',
                criteria=[
                    _clip(f'States whether the capsule method, source anchors and build settings apply to {target_profile} ({detail}), citing the files read.'),
                    'Names every target adaptation needed beyond the capsule method, or states that none is needed.',
                ],
            )]
            if raw_outs:
                outputs = [dict(name=o.get('name') or o.get('port'), kind=o['kind'], criteria=[_clip(step['objective'])]) for o in raw_outs]
            entry = node(
                sid, 'inspect', 'preflight', step['objective'], preds, inputs, outputs,
                [dict(output=o['name'], review=True) for o in outputs], [],
                scaps + HELPFUL['inspect'], step_limits=s_lim, step_criteria=s_crit, ws_override=ws_ovr,
            )
            if unit_lbl in preflight:
                derive(sid, 'choice', f'preflight added: {preflight[unit_lbl]["why"]}')
            node_by_id[sid] = entry
            continue

        if skind == 'inspect':
            inputs = _pull_inputs('inspect', preds) if preds else [dict(name='source', **{'from': 'task:source'})]
            outputs = [dict(
                name='engine_map', kind='evidence',
                criteria=[f'Names engine revision {revision}, target {target_profile}, and source anchors for {", ".join(sorted(units))}.'],
            )]
            if raw_outs:
                outputs = [dict(name=o.get('name') or o.get('port'), kind=o['kind'], criteria=[_clip(step['objective'])]) for o in raw_outs]
            entry = node(
                sid, 'inspect', 'inspect', step['objective'], preds, inputs, outputs,
                [dict(output=o['name']) for o in outputs], [],
                scaps + HELPFUL['inspect'], step_limits=s_lim, step_criteria=s_crit, ws_override=ws_ovr,
            )
            node_by_id[sid] = entry
            continue

        if skind == 'integrate':
            diff_caps = [cid for cid in scaps if capsules[cid]['builder']]
            inputs = _pull_inputs('integrate', preds, preferred_kinds=('evidence', 'diff'))
            outputs, verifiers, req_ids, covered = [], [], [], []
            for idx, cid in enumerate(diff_caps):
                capsule = capsules[cid]
                component = capsule['component']
                is_converter = component.get('change_kind') == 'converter'
                has_pack_v = is_converter and 'verify_pack' in capsule['verifiers']
                name = 'change' if len(diff_caps) == 1 else f'change_{idx + 1}'
                matched_ac = _matching_ac(cid, is_pack=is_converter)
                req_ids.extend(c['id'] for c in matched_ac)
                criteria = [f'Implements the {component["name"].replace("_", " ")} as {cid} describes, touching only the files its source map allows.']
                criteria.extend(_clip(c['description']) for c in matched_ac)
                criteria.extend(_clip(o) for o in component['correctness_obligations'][:4])
                criteria.extend(_clip(n) for n in notes)
                outputs.append(dict(name=name, kind='diff', criteria=criteria[:MAX_CRITERIA]))
                verifiers.append(dict(output=name, verifier=cid + '.verify',
                                      stage='fixture' if has_pack_v else 'native CC execution', review=True))
                if has_pack_v:
                    pack_criteria = [_clip(c['description']) for c in matched_ac] or [
                        f'Converted weight pack passes {cid}.verify_pack and lists per-file sha256 and tensor census.'
                    ]
                    outputs.append(dict(name='converted_pack', kind='evidence', criteria=pack_criteria[:MAX_CRITERIA]))
                    verifiers.append(dict(output='converted_pack', verifier=cid + '.verify_pack',
                                          stage='native CC execution', review=True))
                if cid in cap_to_unit:
                    covered.append(cap_to_unit[cid])
                if cid in selected_reasons:
                    derive(sid, 'selected_capsule', f'{cid}: {selected_reasons[cid]}')
            if not diff_caps:
                outputs = [
                    dict(name=(o.get('name') or o.get('port')) if raw_outs else 'integrated',
                         kind=o['kind'] if raw_outs else 'diff',
                         criteria=[_clip(step['objective'])])
                    for o in (raw_outs or [{}])
                ]
                verifiers = [dict(output=o['name'], review=True) for o in outputs]
            cap_ver = (diff_caps[0] + '.verify') if diff_caps else None
            diff_units_covered[sid] = sorted(set(covered))
            entry = node(
                sid, 'integrate', 'integrate', step['objective'], preds, inputs, outputs, verifiers,
                req_ids, scaps + HELPFUL['merge'], capability=cap_ver,
                step_limits=s_lim, step_criteria=s_crit, ws_override=ws_ovr,
            )
            node_by_id[sid] = entry
            continue

        if skind == 'merge':
            inputs = _pull_inputs('integrate', preds, preferred_kinds=('diff', 'evidence'), all_matching=True)
            covered = sorted({u for p in preds for u in diff_units_covered.get(p, [])})
            diff_units_covered[sid] = covered
            overlap = []
            for i, a in enumerate(covered):
                for b in covered[i + 1:]:
                    pair = pairs_map.get(frozenset((a, b)))
                    if pair and pair['files']:
                        overlap.append(_clip(f'Where {a} and {b} both change {", ".join(pair["files"])}, '
                                             'the merge keeps both behaviours and each switch still works alone.'))
            has_downstream_merge = any(
                oid != sid and sid in ancestors.get(oid, ()) for oid in merge_ids
            ) or any(
                other['kind'] == 'merge' and other['id'] != sid and sid in eff_deps.get(other['id'], ())
                for other in ordered_steps
            )
            is_final = not has_downstream_merge
            criteria = [
                f'Contains the changes of {", ".join(covered) or "upstream branches"} and nothing else.',
                'Each component keeps its own switch and stays off by default; any one can be enabled alone.',
            ] + overlap
            if is_final:
                criteria.extend(_clip(c['description']) for c in correctness_ac if 'pack' not in c['id'])
            merge_reqs = [c['id'] for c in correctness_ac if 'pack' not in c['id']] if is_final else []
            entry = node(
                sid, 'integrate', 'merge', step['objective'], preds, inputs,
                [dict(name='combined', kind='diff', criteria=criteria[:MAX_CRITERIA])],
                [dict(output='combined', review=True)], merge_reqs, scaps + HELPFUL['merge'],
                step_limits=s_lim, step_criteria=s_crit, ws_override=ws_ovr,
            )
            if isinstance(ir.get('merge'), dict):
                derive(sid, 'choice', f'merge option {ir["merge"]["option"]}: {ir["merge"]["why"]}')
            node_by_id[sid] = entry
            continue

        if skind == 'build':
            tool_cid = _has_tool_compiler(step, capsules)
            if tool_cid:
                capsule = capsules[tool_cid]
                matched_ac = _matching_ac(tool_cid, is_pack=True)
                inputs = _pull_inputs('build', preds, preferred_kinds=('evidence', 'diff', 'source_bundle'))
                outputs, verifiers = [], []
                if 'verify_recipe' in capsule['verifiers']:
                    outputs.append(dict(name='recipe', kind='evidence',
                                        criteria=['Names source pack digest, per-role target types and imatrix digest.']))
                    verifiers.append(dict(output='recipe', verifier=tool_cid + '.verify_recipe', stage='fixture', review=True))
                pack_criteria = [_clip(c['description']) for c in matched_ac] + [_clip(n) for n in notes]
                if not pack_criteria:
                    pack_criteria = [f'Output pack passes {tool_cid}.verify_pack.']
                outputs.append(dict(name='compiled_pack', kind='evidence', criteria=pack_criteria[:MAX_CRITERIA]))
                verifiers.append(dict(output='compiled_pack', verifier=tool_cid + '.verify_pack',
                                      stage='native CC execution', review=True))
                has_later_packaging = bool(final_packaging_builds - {sid})
                if not has_later_packaging or (raw_outs and any(o['kind'] in {'source_bundle', 'image'} for o in raw_outs)):
                    outputs.append(dict(name='sources', kind='source_bundle', criteria=pack_criteria[:MAX_CRITERIA]))
                    verifiers.append(dict(output='sources'))
                if tool_cid in selected_reasons:
                    derive(sid, 'selected_capsule', f'{tool_cid}: {selected_reasons[tool_cid]}')
                entry = node(
                    sid, 'build', 'build', step['objective'], preds, inputs, outputs, verifiers,
                    [c['id'] for c in matched_ac], scaps + ['engine.precision_lab'],
                    capability=tool_cid + '.verify_pack',
                    extra_evidence=('mandatory_checks', 'semantic_assessment'),
                    step_limits=s_lim, step_criteria=s_crit, ws_override=ws_ovr,
                )
            else:
                inputs = _pull_inputs('build', preds, preferred_kinds=('diff', 'evidence'), all_matching=True,
                                      skip_ports={'sources', 'image'})
                build_reqs = [c['id'] for c in constraint_ac] + [c['id'] for c in correctness_ac if c['id'] == 'cold_smoke']
                build_criteria = [f'One final source bundle for {model_name} against pinned commit {revision} ({target_profile}).']
                build_criteria.extend(_clip(c['description']) for c in constraint_ac)
                if raw_outs:
                    outputs = [dict(name=o.get('name') or o.get('port'), kind=o['kind'], criteria=build_criteria[:MAX_CRITERIA]) for o in raw_outs]
                else:
                    outputs = [
                        dict(name='sources', kind='source_bundle', criteria=build_criteria[:MAX_CRITERIA]),
                        dict(name='image', kind='image', required=False,
                             criteria=['Optional: a factory-built image of the final build with its build receipt.']),
                    ]
                verifiers = [dict(output=o['name']) for o in outputs]
                entry = node(
                    sid, 'build', 'build', step['objective'], preds, inputs, outputs, verifiers,
                    build_reqs, scaps + HELPFUL['build'],
                    step_limits=s_lim, step_criteria=s_crit, ws_override=ws_ovr,
                )
            node_by_id[sid] = entry
            continue

        if skind == 'deliver':
            ship_ref = None
            for p in preds:
                pnode = node_by_id.get(p)
                if not pnode:
                    continue
                out = next((o for o in pnode.get('outputs', []) if o['kind'] in {'source_bundle', 'image'}), None)
                if out:
                    ship_ref = (p, out['name'])
                    break
            if ship_ref is None:
                for p in reversed(list(node_by_id)):
                    pnode = node_by_id[p]
                    out = next((o for o in pnode.get('outputs', []) if o['kind'] in {'source_bundle', 'image'}), None)
                    if out:
                        ship_ref = (p, out['name'])
                        if p not in preds:
                            preds.append(p)
                        break
            src_node, src_port = ship_ref or ('build_candidate', 'sources')
            deliver_criteria = [
                f'Delivers the verified artifact against pinned commit {revision} on {target_profile}.',
                'Verifies every correctness check, metric and constraint in acceptance_criteria.',
            ]
            for item in ac_items:
                line = item['description'] + (f" (target: {item['threshold']})" if item.get('threshold') else '')
                deliver_criteria.append(_clip(f"[{item['id']}] {line}"))
            entry = node(
                sid, 'deliver', 'deliver', step['objective'], preds,
                [dict(name='sources', **{'from': f'{src_node}.{src_port}'})],
                [dict(name='lab_request', kind='lab_request', criteria=deliver_criteria[:MAX_CRITERIA])],
                [dict(output='lab_request')], all_ac_ids, scaps + HELPFUL['deliver'],
                step_limits=s_lim, step_criteria=s_crit, ws_override=ws_ovr,
            )
            entry['hands_to'] = 'lab_manager'
            node_by_id[sid] = entry
            continue

        # Generic autonomous step kinds: investigate, decide, tune, measure, accept, report
        preferred = ('source_bundle', 'image', 'evidence', 'diff') if skind in {'measure', 'accept', 'report'} else ('evidence', 'diff', 'source_bundle')
        inputs = _pull_inputs(skind, preds, preferred_kinds=preferred)
        is_post_or_eval = skind in {'measure', 'accept', 'report', 'tune'} or sid in deliver_deps
        stage_ac = (metric_ac or correctness_ac or ac_items) if is_post_or_eval else []
        stage_req_ids = [c['id'] for c in stage_ac]
        stage_criteria = [_clip(c['description']) for c in stage_ac] or [_clip(step['objective'])]

        verifier_cap = None
        for cid in scaps:
            cap = capsules.get(cid)
            if not cap or not cap.get('verifiers'):
                continue
            v0 = cap['verifiers'][0]
            needed = set(cap['capabilities'][v0]['changes'])
            if cid in selected_reasons or needed <= (allowed & {'process.exec', 'workspace.read'}):
                verifier_cap = f'{cid}.{v0}'
                break

        default_kind = 'diff' if skind == 'tune' else 'evidence'
        default_name = 'smoke_evidence' if sid == 'verify_smoke' else ('tuned_diff' if skind == 'tune' else 'stage_out')
        outs_spec = raw_outs or [{'name': default_name, 'kind': default_kind}]
        outputs = [
            dict(name=_slug_id(o.get('name') or o.get('port')), kind=o['kind'], criteria=stage_criteria[:MAX_CRITERIA])
            for o in outs_spec
        ]
        verifiers = []
        for idx, o in enumerate(outputs):
            ventry: dict = {'output': o['name']}
            if idx == 0 and verifier_cap and o['kind'] in {'diff', 'evidence'}:
                ventry['verifier'] = verifier_cap
            if skind in {'investigate', 'decide', 'tune', 'accept', 'measure'}:
                ventry['review'] = bool(skind in {'investigate', 'decide', 'tune', 'accept'} or verifier_cap)
            verifiers.append(ventry)

        for cid in scaps:
            if cid in selected_reasons:
                derive(sid, 'selected_capsule', f'{cid}: {selected_reasons[cid]}')
        entry = node(
            sid, skind, skind, step['objective'], preds, inputs, outputs, verifiers,
            stage_req_ids, scaps + HELPFUL.get(skind, ['factory.source_workbench']),
            capability=verifier_cap, step_limits=s_lim, step_criteria=s_crit, ws_override=ws_ovr,
        )
        node_by_id[sid] = entry

    for entry in nodes[:-1]:
        entry['hands_to'] = next((n['node_id'] for n in nodes if entry['node_id'] in n.get('predecessors', [])), '')
    if nodes and nodes[-1]['kind'] == 'deliver':
        nodes[-1]['hands_to'] = 'lab_manager'

    known = {n['node_id']: n for n in nodes}
    for key in set(ir.get('criteria') or {}) | set(ir.get('limits') or {}):
        if key not in known:
            problems.append(f'{key}: no such step; steps are {sorted(known)}')
    if problems:
        raise CompileError(problems)

    document = dict(format='factory.node-contracts/1', nodes=nodes)
    plan = dict(
        format='factory.plan/1',
        planner=PLANNER,
        nodes=[
            dict(node_id=n['node_id'], node_contract=n['node_id'], depends_on=list(n.get('predecessors', [])))
            for n in nodes
        ],
    )
    return document, plan, log


def compile_to_tla(ir, selection, task_input, *, max_parallel=None, attempts=None, catalog=None):
    """Compile autonomous Plan IR into self-contained ``graph.tla`` plus intermediates."""
    document, plan, derivation = compile_plan(ir, selection, task_input, catalog=catalog)
    graph_tla = tla_graph.render_graph_tla(
        document, task_input, plan, max_parallel=max_parallel, attempts=attempts,
    )
    return graph_tla, document, plan, derivation
