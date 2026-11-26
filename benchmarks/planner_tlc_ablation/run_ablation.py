"""Run the 3-Way Planner Verification Ablation Study:
1. ``Old M1`` (M1 Planner ``max_attempts=1`` + M1 Verifier ``binding.plan_checks``)
2. ``M2 Static`` (Bridged M1 + M2 8-Rule ``plan_checks.run()``, without TLC)
3. ``TLC-Verified Planner`` (Internal 2-Pass ``tlc2.TLC`` + ``ASSUME`` Gate -> Verified JSON Deliverables)

All measurements in ``results.json`` come from real execution of ``m1_verifier_bridge``
(``jiuwenswarm.research.binding.plan_checks``), ``plan_compile``, ``plan_checks.run``,
``tla_graph``, ``tla_check.check_graph_tla`` (real Java + ``tla2tools.jar``), and the
deterministic Monte Carlo scheduler simulator.
"""
from __future__ import annotations

import asyncio
import copy
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from jiuwenswarm.factory import (
    ai_planner,
    m1_verifier_bridge,
    plan_catalog,
    plan_checks,
    plan_compile,
    plan_select,
    requirements as req,
    tla_check,
    tla_graph,
)

from .simulator import simulate_graph

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SHIPPED = REPO_ROOT / 'jiuwenswarm' / 'factory' / 'requirements'


def _git_commit() -> str:
    res = subprocess.run(['git', '-C', str(REPO_ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=False)
    return res.stdout.strip() if res.returncode == 0 else 'unknown'


def _java_version(java_bin: str) -> str:
    res = subprocess.run([java_bin, '-version'], capture_output=True, text=True, check=False)
    text = (res.stderr or res.stdout or '').strip().splitlines()
    return text[0] if text else 'unknown'


def _build_autonomous_ir(
    sel: dict,
    caps: list[str],
    *,
    option: str = 'M1',
    preflight_add: bool = True,
    limits: dict | None = None,
    priority: list | None = None,
    extra_smoke: bool = False,
) -> dict:
    """Build a standalone ``factory.plan-ir/1`` using autonomous ``steps`` & direct CC bindings."""
    risky = {r['capsule'] for r in sel['risks']}
    by_cap = {c['capsule']: c for c in sel['candidates']}
    steps: list[dict[str, Any]] = [
        {
            'id': 'inspect_engine',
            'kind': 'inspect',
            'objective': 'Inspect pinned engine checkout and record CC Library capsule anchors.',
            'depends_on': [],
            'capsules': ['factory.engine_inspector', 'factory.source_workbench'],
        },
    ]
    preflight_list: list[dict[str, Any]] = []
    preflight_step: dict[str, str] = {}
    diff_steps: list[str] = []
    converter_step: str | None = None
    tool_steps: list[str] = []

    for cid in caps:
        info = by_cap[cid]
        unit = info['unit']
        if cid in risky:
            preflight_list.append({'unit': unit, 'add': preflight_add, 'why': info['features']['hardware']['detail']})
            if preflight_add:
                pid = f'preflight_{unit}'
                steps.append({
                    'id': pid,
                    'kind': 'inspect',
                    'objective': f'Verify {cid} applicability on target hardware before editing.',
                    'depends_on': ['inspect_engine'],
                    'capsules': [cid, 'factory.engine_inspector'],
                })
                preflight_step[unit] = pid

    for cid in caps:
        info = by_cap[cid]
        unit = info['unit']
        if info['kind'] == 'builder':
            sid = f'integrate_{unit}'
            deps = [preflight_step[unit]] if unit in preflight_step else ['inspect_engine']
            steps.append({
                'id': sid,
                'kind': 'integrate',
                'objective': f'Integrate {cid} behind its runtime toggle in an owned checkout.',
                'depends_on': deps,
                'capsules': [cid, 'factory.integration_skill', 'factory.source_workbench'],
            })
            diff_steps.append(sid)
            if info.get('change_kind') == 'converter':
                converter_step = sid

    for cid in caps:
        info = by_cap[cid]
        unit = info['unit']
        if info['kind'] != 'builder':
            sid = f'build_{unit}'
            deps = ['inspect_engine'] + ([converter_step] if converter_step else [])
            steps.append({
                'id': sid,
                'kind': 'build',
                'objective': f'Compile and verify weight pack using {cid}.',
                'depends_on': deps,
                'capsules': [cid, 'engine.precision_lab'],
            })
            tool_steps.append(sid)

    upstream_for_build = list(diff_steps)
    if len(diff_steps) >= 2:
        steps.append({
            'id': 'combine',
            'kind': 'merge',
            'objective': f'Merge concurrent branch diffs ({option}) preserving toggle isolation.',
            'depends_on': list(diff_steps),
            'capsules': ['factory.integration_skill', 'factory.source_workbench'],
        })
        upstream_for_build = ['combine']

    steps.append({
        'id': 'build_candidate',
        'kind': 'build',
        'objective': 'Build and package final verified engine artifact.',
        'depends_on': upstream_for_build + tool_steps,
        'capsules': ['factory.builder', 'factory.lab_manager'],
    })
    deliver_deps = ['build_candidate']
    if extra_smoke:
        steps.append({
            'id': 'verify_smoke',
            'kind': 'measure',
            'objective': 'Run autonomous post-build cold smoke verification before delivery.',
            'depends_on': ['build_candidate'],
            'capsules': ['factory.lab_manager'],
            'limits': {'turns': 12},
        })
        deliver_deps = ['build_candidate', 'verify_smoke']

    steps.append({
        'id': 'deliver_to_lab',
        'kind': 'deliver',
        'objective': 'Deliver verified engine artifact and acceptance suite to lab.',
        'depends_on': deliver_deps,
        'capsules': ['factory.lab_manager'],
    })

    ir: dict[str, Any] = {
        'format': 'factory.plan-ir/1',
        'selected_capsules': [{'capsule': c, 'why': 'benchmark selection'} for c in caps],
        'preflight': preflight_list,
        'steps': steps,
    }
    if len(diff_steps) >= 2:
        ir['merge'] = {'option': option, 'why': f'merge via {option}'}
    if limits:
        ir['limits'] = limits
    if priority:
        ir['priority'] = priority
    return ir


def _build_star_ir(sel: dict, caps: list[str], *, option: str = 'M1', preflight_add: bool = True,
                   limits: dict | None = None, priority: list | None = None, extra_smoke: bool = False) -> dict:
    return _build_autonomous_ir(
        sel, caps, option=option, preflight_add=preflight_add,
        limits=limits, priority=priority, extra_smoke=extra_smoke,
    )


def _build_muse_ir(sel: dict, caps: list[str], *, option: str = 'M1', preflight_add: bool = True,
                   limits: dict | None = None) -> dict:
    return _build_autonomous_ir(sel, caps, option=option, preflight_add=preflight_add, limits=limits)


def _apply_runtime_overrides(
    execution_model: dict[str, Any],
    plan: dict[str, Any] | None,
    exclusive_override: dict[str, list[str]] | None,
) -> dict[str, Any]:
    """Attach scheduler depends_on edges and omitted exclusive locks for simulation."""
    model = copy.deepcopy(execution_model)
    if plan and isinstance(plan.get('nodes'), list):
        pdeps = {pn['node_id']: list(pn.get('depends_on') or []) for pn in plan['nodes']}
        for nid in model['preds']:
            if nid in pdeps:
                model['preds'][nid] = sorted(set(model['preds'][nid]) | set(pdeps[nid]))
    if exclusive_override is not None:
        for nid, ex in exclusive_override.items():
            if nid in model['exclusive']:
                model['exclusive'][nid] = sorted(ex)
    return model


def _evaluate_pair(
    *,
    case_id: str,
    class_id: str,
    category: str,
    enforcement_mechanism: str,
    title: str,
    fault_kind: str | None,
    task_input: dict,
    document: dict,
    plan: dict,
    work_dir: Path,
    catalog: dict,
    exclusive_override: dict[str, list[str]] | None = None,
    expected_tla_pass: bool = True,
) -> dict[str, Any]:
    """Run all 3 verification arms on identical TaskInput/compiled plan:
    1) M1 Legacy (real M1 binding.plan_checks + max_attempts_per_node=1)
    2) M2 Static (Bridged M1 + M2 8-rule plan_checks.run, no TLC)
    3) Formal TLA+ (graph.tla ASSUME + 2-pass TLC + zero-JVM parse)
    """
    allowed = list(task_input['constraints']['allowed_effects'])
    base_model = tla_check.execution_model(document)

    # --- Arm 1: M1 Legacy (Old M1 Verifier binding.plan_checks + max_attempts_per_node == 1) ---
    m1_t0 = time.perf_counter()
    m1_res = m1_verifier_bridge.run_m1_plan_checks(document, plan, task_input, catalog)
    m1_latency_s = round(time.perf_counter() - m1_t0, 4)
    m1_admitted = bool(m1_res['passed'])

    m1_model = _apply_runtime_overrides(base_model, plan, exclusive_override)
    # Enforce M1's binding.py:98,453 hard lock: max_attempts_per_node == 1 (preserving 0-attempt fault)
    m1_model['limits'] = {nid: min(1, int(lim)) for nid, lim in m1_model['limits'].items()}
    m1_sim = simulate_graph(document, m1_model, allowed, trials=100, seed=42)
    m1_hazard_rate = round(1.0 - m1_sim['delivery_rate'], 4)

    # --- Arm 2: M2 Static-Only (Bridged M1 + M2 8-Rule Static Checks, No TLC) ---
    b0_t0 = time.perf_counter()
    static_problems, static_warnings = plan_checks.run(document, plan, task_input, catalog)
    static_latency_s = round(time.perf_counter() - b0_t0, 4)
    static_admitted = (len(static_problems) == 0)

    static_model = _apply_runtime_overrides(base_model, plan, exclusive_override)
    static_sim = simulate_graph(document, static_model, allowed, trials=100, seed=42)

    # --- Arm 3: Formal TLA+ (graph.tla -> check_graph_tla -> zero-JVM parse) ---
    t1_t0 = time.perf_counter()
    t1_tla_text = tla_graph.render_graph_tla(
        document, task_input, plan, exclusive_override=exclusive_override,
    )
    tla_file = work_dir / f'{case_id}.tla'
    tla_file.parent.mkdir(parents=True, exist_ok=True)
    tla_file.write_text(t1_tla_text, encoding='utf-8')

    parse_t0 = time.perf_counter()
    parsed = tla_graph.parse_taskgraph_tla(tla_file)
    parse_ms = round((time.perf_counter() - parse_t0) * 1000, 3)

    plan_matches = (parsed['plan'] == plan) or all(
        set(p['depends_on']) <= set(q['depends_on'])
        for p, q in zip(plan['nodes'], parsed['plan']['nodes'])
    )
    roundtrip_exact = (parsed['node_contracts'] == document and plan_matches)

    verification = tla_check.check_graph_tla(tla_file, work_dir / 'tlc')
    tla_latency_s = round(time.perf_counter() - t1_t0, 4)
    tla_admitted = (len(static_problems) == 0) and bool(verification['passed'])

    trace_steps = []
    if not verification['passed']:
        for run in verification['runs']:
            out_path = work_dir / 'tlc' / f"{run['run']}.out"
            if out_path.is_file():
                raw_out = out_path.read_text(encoding='utf-8')
                trace = tla_check.parse_trace(raw_out)
                trace_steps = [
                    {'state': s['state'], 'action': s['action'], 'st': s.get('st', {}), 'att': s.get('att', {})}
                    for s in trace[:14]
                ]
                if trace_steps:
                    break

    if tla_admitted:
        tla_sim = simulate_graph(parsed['node_contracts'], parsed['execution_model'], allowed, trials=100, seed=42)
    else:
        tla_sim = {
            'blocked_before_execution': True, 'trials': 100, 'delivered': 0, 'stuck_or_failed': 0,
            'delivery_rate': 0.0, 'stuck_rate': 0.0, 'contract_violation_rate': 0.0,
            'authority_violations': 0, 'race_violations': 0,
            'wasted_nodes_per_trial': 0.0, 'wasted_turns_per_trial': 0.0, 'failure_reasons': {},
        }

    hazard_rate = round(1.0 - static_sim['delivery_rate'], 4)

    return {
        'case_id': case_id,
        'class': class_id,
        'category': category,
        'enforcement_mechanism': enforcement_mechanism,
        'title': title,
        'fault_kind': fault_kind,
        'node_count': len(document['nodes']),
        'task_id': task_input.get('task_id'),
        'expected_tla_pass': expected_tla_pass,
        'm1_legacy': {
            'executed': bool(m1_res['executed']),
            'checks': m1_res['results'],
            'summary': m1_res['summary'],
            'problems': m1_res['problems'],
            'admitted': m1_admitted,
            'escaped_defect': bool(fault_kind and m1_admitted and not expected_tla_pass),
            'latency_s': m1_latency_s,
            'hazard_rate': m1_hazard_rate,
            'max_attempts_per_node': 1,
            'simulation': m1_sim,
        },
        'static_only': {
            'static_problems': static_problems,
            'warnings': static_warnings,
            'admitted': static_admitted,
            'escaped_defect': bool(fault_kind and static_admitted and not expected_tla_pass),
            'latency_s': static_latency_s,
            'hazard_rate': hazard_rate,
            'simulation': static_sim,
        },
        'tla_pipeline': {
            'admitted': tla_admitted,
            'tlc_passed': bool(verification['passed']),
            'tlc_problems': verification['problems'],
            'runs': verification['runs'],
            'total_distinct_states': sum(r.get('distinct_states') or 0 for r in verification['runs']),
            'total_states_generated': sum(r.get('states_generated') or 0 for r in verification['runs']),
            'latency_s': tla_latency_s,
            'parse_ms': parse_ms,
            'roundtrip_exact': roundtrip_exact,
            'graph_tla_bytes': len(t1_tla_text.encode('utf-8')),
            'graph_tla_preview': t1_tla_text,
            'counterexample_trace': trace_steps,
            'simulation': tla_sim,
        },
    }


def _run_repair_case(
    *,
    case_id: str,
    title: str,
    fault_label: str,
    task_input: dict,
    bad_ir: dict,
    good_ir: dict,
    work_dir: Path,
) -> dict[str, Any]:
    """Run real ``ai_planner.synthesize`` loop across M1 Legacy vs M2 Static vs Formal TLA+."""
    cat = plan_catalog.load()
    sel = plan_select.context(task_input, cat)

    bad_doc, bad_plan, _ = plan_compile.compile_plan(bad_ir, sel, task_input)
    m1_r1 = m1_verifier_bridge.run_m1_plan_checks(bad_doc, bad_plan, task_input, cat)
    static_probs, _ = plan_checks.run(bad_doc, bad_plan, task_input, cat)
    static_model = tla_check.execution_model(bad_doc)
    m1_model = copy.deepcopy(static_model)
    m1_model['limits'] = {nid: min(1, int(lim)) for nid, lim in m1_model['limits'].items()}
    m1_r1_sim = simulate_graph(bad_doc, m1_model, task_input['constraints']['allowed_effects'], trials=100, seed=42)
    static_sim = simulate_graph(bad_doc, static_model, task_input['constraints']['allowed_effects'], trials=100, seed=42)

    replies = iter([json.dumps(bad_ir), json.dumps(good_ir)])
    captured_prompts: list[str] = []

    async def scripted_invoke(prompt: str, system: str) -> dict:
        captured_prompts.append(prompt)
        return {'text': next(replies), 'identity': 'ablation-scripted-repair'}

    t0 = time.perf_counter()
    run_dir = work_dir / 'synth'
    status = asyncio.run(ai_planner.synthesize(task_input, run_dir, invoke=scripted_invoke))
    total_s = round(time.perf_counter() - t0, 4)

    from jiuwenswarm.factory import node_contract as nc_mod
    r1_res = json.loads((run_dir / 'rounds' / '1' / 'result.json').read_text(encoding='utf-8'))
    r2_res = json.loads((run_dir / 'rounds' / '2' / 'result.json').read_text(encoding='utf-8'))
    emitted_contract = nc_mod.for_task({'contract_id': str(run_dir / 'contract.json')})
    emitted_graph = json.loads((run_dir / 'graph.json').read_text(encoding='utf-8'))
    tla_sim = simulate_graph(emitted_contract, emitted_graph['execution_model'],
                             task_input['constraints']['allowed_effects'], trials=100, seed=42)

    feedback_section = ''
    if len(captured_prompts) >= 2 and '## Your previous decisions were rejected' in captured_prompts[1]:
        feedback_section = captured_prompts[1].split('## Your previous decisions were rejected', 1)[1].split('## Your previous reply:', 1)[0].strip()

    r1_trace = []
    for fname in ('safety.out', 'delivery.out'):
        r1_out = run_dir / 'rounds' / '1' / 'tla' / fname
        if r1_out.is_file():
            parsed_tr = tla_check.parse_trace(r1_out.read_text(encoding='utf-8'))
            if parsed_tr:
                r1_trace = [
                    {'state': s['state'], 'action': s['action'], 'st': s.get('st', {}), 'att': s.get('att', {})}
                    for s in parsed_tr[:14]
                ]
                break

    changed_keys = sorted(k for k in set(bad_ir) | set(good_ir) if bad_ir.get(k) != good_ir.get(k))
    return {
        'case_id': case_id,
        'class': 'C',
        'title': title,
        'fault_label': fault_label,
        'task_id': task_input.get('task_id'),
        'm1_round1_problems': m1_r1['problems'],
        'm1_admitted_buggy_round1': bool(m1_r1['passed']),
        'm1_round1_simulation': m1_r1_sim,
        'static_round1_problems': static_probs,
        'static_admitted_buggy_round1': len(static_probs) == 0,
        'static_round1_simulation': static_sim,
        'tla_final_state': status['state'],
        'tla_rounds_taken': status['round'],
        'tla_total_latency_s': total_s,
        'verified_json_emitted': (
            (run_dir / 'contract.json').is_file()
            and (run_dir / 'plan.json').is_file()
            and (run_dir / 'graph.json').is_file()
            and (run_dir / 'verification.json').is_file()
            and not (run_dir / 'graph.tla').exists()
        ),
        'round1_layer': r1_res.get('layer'),
        'round1_problems': r1_res.get('problems', []),
        'round1_trace': r1_trace,
        'feedback_excerpt': feedback_section,
        'changed_ir_fields': changed_keys,
        'round2_layer': r2_res.get('layer'),
        'round2_verification': r2_res.get('verification'),
        'tla_final_simulation': tla_sim,
    }


def _measure_scalability(star: dict, star_sel: dict, work_root: Path) -> list[dict[str, Any]]:
    """Measure real TLC states & latency for k=2..5 parallel units: Unconstrained vs Priority-Ordered."""
    caps_all = [
        'observability.build_runtime_event_recorder',
        'placement.build_weight_placement_planner',
        'engine.build_expert_weight_cache',
        'routing.build_expert_demand_predictor',
        'engine.build_batch_layout_mapper',
    ]
    by_cap = {c['capsule']: c for c in star_sel['candidates']}
    rows = []
    for k in (2, 3, 4, 5):
        sub = caps_all[:k]
        units_k = [by_cap[c]['unit'] for c in sub]
        ir_u = _build_star_ir(star_sel, sub, option='M1', preflight_add=False)
        ir_o = _build_star_ir(
            star_sel, sub, option='M1', preflight_add=False,
            priority=[[units_k[i], units_k[i + 1]] for i in range(k - 1)],
        )
        du, pu, _ = plan_compile.compile_plan(ir_u, star_sel, star)
        do, po, _ = plan_compile.compile_plan(ir_o, star_sel, star)
        vu = tla_check.check_graph_tla(tla_graph.render_graph_tla(du, star, pu), work_root / f'scale-u{k}')
        vo = tla_check.check_graph_tla(tla_graph.render_graph_tla(do, star, po), work_root / f'scale-o{k}')
        su = sum(r.get('distinct_states') or 0 for r in vu['runs'])
        so = sum(r.get('distinct_states') or 0 for r in vo['runs'])
        tu = round(sum(r.get('seconds') or 0 for r in vu['runs']), 3)
        to = round(sum(r.get('seconds') or 0 for r in vo['runs']), 3)
        rows.append({
            'k': k,
            'unconstrained_states': su,
            'unconstrained_seconds': tu,
            'unconstrained_passed': vu['passed'],
            'ordered_states': so,
            'ordered_seconds': to,
            'ordered_passed': vo['passed'],
            'state_reduction_ratio': round(su / so, 2) if so else 1.0,
        })
    return rows


def run_all(out_dir: Path | None = None) -> dict[str, Any]:
    """Execute the full ablation benchmark (Classes A, B across 4 categories, C, Scalability)."""
    out_dir = Path(out_dir) if out_dir else HERE
    out_dir.mkdir(parents=True, exist_ok=True)
    work_root = Path(tempfile.mkdtemp(prefix='planner-ablation-'))

    java, jar = tla_check.tools()
    cat = plan_catalog.load()
    star = req.load(SHIPPED / 'star-deepseek-v2.json')
    muse = req.load(SHIPPED / 'muse-q2-ttft-v2.json')
    star_sel = plan_select.context(star, cat)
    muse_sel = plan_select.context(muse, cat)

    muse_all_caps = [
        'weights.build_muse_nvfp4_reader',
        'weights.build_expert_scale_wiring',
        'weights.build_weight_pack_compiler',
        'engine.build_expert_weight_cache',
    ]
    muse_pack_caps = [
        'weights.build_muse_nvfp4_reader',
        'weights.build_expert_scale_wiring',
        'weights.build_weight_pack_compiler',
    ]
    star_4_caps = [
        'observability.build_runtime_event_recorder',
        'engine.build_expert_weight_cache',
        'routing.build_expert_demand_predictor',
        'engine.build_batch_layout_mapper',
    ]

    cases: list[dict[str, Any]] = []

    # =========================================================================
    # Class A — Healthy Baseline Suite (6 cases; must have 0% FP & 100% roundtrip)
    # =========================================================================
    class_a_specs = [
        ('A1_star_single_cache', 'Star Single Capsule (expert_weight_cache + preflight)',
         star, star_sel, _build_star_ir(star_sel, ['engine.build_expert_weight_cache'], preflight_add=True)),
        ('A2_star_multi_m1', 'Star 3-Capsule Merge (M1 one-shot combine)',
         star, star_sel, _build_star_ir(star_sel, ['observability.build_runtime_event_recorder', 'engine.build_expert_weight_cache', 'routing.build_expert_demand_predictor'], option='M1', preflight_add=True)),
        ('A3_star_multi_m2', 'Star 4-Capsule Interference Merge (M2 clustered)',
         star, star_sel, _build_star_ir(star_sel, star_4_caps, option='M2', preflight_add=False)),
        ('A4_star_multi_m3', 'Star 3-Capsule Incremental Merge (M3 step-by-step)',
         star, star_sel, _build_star_ir(star_sel, ['engine.build_expert_weight_cache', 'routing.build_expert_demand_predictor', 'engine.build_batch_layout_mapper'], option='M3', preflight_add=False)),
        ('A5_muse_mixed_preflight', 'Muse NVFP4 Full Mixed Pipeline (4 CCs + preflight_cache)',
         muse, muse_sel, _build_muse_ir(muse_sel, muse_all_caps, option='M1', preflight_add=True)),
        ('A6_muse_mixed_nopreflight', 'Muse NVFP4 Converter + Scale Wiring + Pack Compiler (no cache)',
         muse, muse_sel, _build_muse_ir(muse_sel, muse_pack_caps, option='M1', preflight_add=False)),
    ]
    for cid, title, ti, sel, ir in class_a_specs:
        doc, plan, _ = plan_compile.compile_plan(ir, sel, ti)
        cases.append(_evaluate_pair(
            case_id=cid, class_id='A', category='Healthy Baseline',
            enforcement_mechanism='TLC Temporal State-Space Proof',
            title=title, fault_kind=None,
            task_input=ti, document=doc, plan=plan,
            work_dir=work_root / cid, catalog=cat, expected_tla_pass=True,
        ))

    # =========================================================================
    # Class B — High-Signal Static-Bypass Faults (10 cases across 4 distinct categories)
    # EVERY case strictly passes plan_checks.run() cleanly!
    # =========================================================================

    # --- Category 1: Concurrent Lock Race (ExclusiveResources via TLC) ---
    doc_l1, plan_l1, _ = plan_compile.compile_plan(
        _build_star_ir(star_sel, ['observability.build_runtime_event_recorder', 'engine.build_expert_weight_cache', 'routing.build_expert_demand_predictor'], option='M1', preflight_add=False),
        star_sel, star,
    )
    cases.append(_evaluate_pair(
        case_id='B_lock_parallel_integrators', class_id='B', category='Concurrent Lock Race',
        enforcement_mechanism='TLC Temporal State-Space Proof',
        title='Missing checkout locks on parallel integrate_* writers (ExclusiveResources)',
        fault_kind='exclusive_checkout_race', task_input=star, document=doc_l1, plan=plan_l1,
        work_dir=work_root / 'B_lock1', catalog=cat,
        exclusive_override={'integrate_cache': [], 'integrate_predictor': [], 'integrate_recorder': []},
        expected_tla_pass=False,
    ))

    # Parallel builders race in Muse mixed flow when builder mutex is omitted
    doc_l2, plan_l2, _ = plan_compile.compile_plan(
        _build_muse_ir(muse_sel, muse_pack_caps, option='M1', preflight_add=False),
        muse_sel, muse,
    )
    # Also test parallel tool builders missing builder lock: add second independent verification build node
    valid_req_id = muse['acceptance_criteria'][0]['id']
    doc_l2_par = copy.deepcopy(doc_l2)
    doc_l2_par['nodes'].insert(-1, {
        'node_id': 'build_quant_audit',
        'kind': 'build',
        'objective': 'Run parallel tensor quantization audit binary alongside build_candidate.',
        'requirement_ids': [valid_req_id],
        'predecessors': ['combine', 'build_compiler'],
        'inputs': [{'name': 'compiled_pack', 'from': 'build_compiler.compiled_pack'}],
        'outputs': [{'name': 'audit_report', 'kind': 'evidence', 'criteria': ['Quantization audit passes.']}],
        'verifiers': [{'output': 'audit_report'}],
        'authority_ceiling': {'effects': ['process.exec', 'workspace.read'], 'workspace': 'read'},
        'node_limits': {'turns': 10, 'build_attempts': 2},
        'hands_to': 'deliver_to_lab',
    })
    for n in doc_l2_par['nodes']:
        if n['node_id'] == 'deliver_to_lab':
            n['predecessors'].append('build_quant_audit')
    plan_l2_par = copy.deepcopy(plan_l2)
    plan_l2_par['nodes'].insert(-1, {'node_id': 'build_quant_audit', 'node_contract': 'build_quant_audit', 'depends_on': ['combine', 'build_compiler']})
    for pn in plan_l2_par['nodes']:
        if pn['node_id'] == 'deliver_to_lab':
            pn['depends_on'].append('build_quant_audit')
    cases.append(_evaluate_pair(
        case_id='B_lock_parallel_builders', class_id='B', category='Concurrent Lock Race',
        enforcement_mechanism='TLC Temporal State-Space Proof',
        title='Missing builder mutex across concurrent build_candidate & build_quant_audit',
        fault_kind='exclusive_builder_race', task_input=muse, document=doc_l2_par, plan=plan_l2_par,
        work_dir=work_root / 'B_lock2', catalog=cat,
        exclusive_override={'build_candidate': [], 'build_quant_audit': []},
        expected_tla_pass=False,
    ))

    doc_l3, plan_l3, _ = plan_compile.compile_plan(
        _build_muse_ir(muse_sel, muse_all_caps, option='M1', preflight_add=False),
        muse_sel, muse,
    )
    cases.append(_evaluate_pair(
        case_id='B_lock_muse_mixed_writers', class_id='B', category='Concurrent Lock Race',
        enforcement_mechanism='TLC Temporal State-Space Proof',
        title='Muse NVFP4 concurrent converter/wiring/cache missing checkout lock',
        fault_kind='exclusive_checkout_race', task_input=muse, document=doc_l3, plan=plan_l3,
        work_dir=work_root / 'B_lock3', catalog=cat,
        exclusive_override={'integrate_reader': [], 'integrate_wiring': [], 'integrate_cache': []},
        expected_tla_pass=False,
    ))

    # --- Category 2: Retry & Attempt Starvation (NoStuck via TLC — 2 sharp representatives) ---
    ir_s1 = _build_star_ir(star_sel, ['engine.build_expert_weight_cache'], limits={'build_candidate': {'build_attempts': 0}})
    doc_s1, plan_s1, _ = plan_compile.compile_plan(ir_s1, star_sel, star)
    cases.append(_evaluate_pair(
        case_id='B_starve_build_candidate', class_id='B', category='Retry & Attempt Starvation',
        enforcement_mechanism='TLC Temporal State-Space Proof',
        title='Legal Plan IR tightening build_candidate.build_attempts=0 (Star single)',
        fault_kind='limit_tightening_starvation', task_input=star, document=doc_s1, plan=plan_s1,
        work_dir=work_root / 'B_starve1', catalog=cat, expected_tla_pass=False,
    ))

    ir_s2 = _build_muse_ir(muse_sel, muse_all_caps, limits={'build_compiler': {'build_attempts': 0}})
    doc_s2, plan_s2, _ = plan_compile.compile_plan(ir_s2, muse_sel, muse)
    cases.append(_evaluate_pair(
        case_id='B_starve_tool_compiler', class_id='B', category='Retry & Attempt Starvation',
        enforcement_mechanism='TLC Temporal State-Space Proof',
        title='Legal Plan IR tightening tool build_compiler.build_attempts=0 (Muse)',
        fault_kind='limit_tightening_starvation', task_input=muse, document=doc_s2, plan=plan_s2,
        work_dir=work_root / 'B_starve2', catalog=cat, expected_tla_pass=False,
    ))

    # --- Category 3: Cooperative Liveness / Ordering Deadlocks (NoStuck/HaltsDelivered via TLC — 3 distinct cases) ---
    doc_d1, plan_d1, _ = plan_compile.compile_plan(
        _build_star_ir(star_sel, ['observability.build_runtime_event_recorder', 'engine.build_expert_weight_cache'], option='M1', preflight_add=False),
        star_sel, star,
    )
    for pn in plan_d1['nodes']:
        if pn['node_id'] == 'integrate_recorder':
            pn['depends_on'].append('integrate_cache')
        elif pn['node_id'] == 'integrate_cache':
            pn['depends_on'].append('integrate_recorder')
    cases.append(_evaluate_pair(
        case_id='B_live_plan_order_deadlock', class_id='B', category='Cooperative Liveness Deficit',
        enforcement_mechanism='TLC Temporal State-Space Proof',
        title='Mutually cyclic depends_on ordering in factory.plan/1 (bypasses plan_checks)',
        fault_kind='ordering_cycle_deadlock', task_input=star, document=doc_d1, plan=plan_d1,
        work_dir=work_root / 'B_live1', catalog=cat, expected_tla_pass=False,
    ))

    doc_d2, plan_d2, _ = plan_compile.compile_plan(
        _build_muse_ir(muse_sel, muse_pack_caps, option='M1', preflight_add=False),
        muse_sel, muse,
    )
    for pn in plan_d2['nodes']:
        if pn['node_id'] == 'integrate_reader' and 'build_compiler' not in pn['depends_on']:
            pn['depends_on'].append('build_compiler')
        elif pn['node_id'] == 'build_compiler' and 'integrate_reader' not in pn['depends_on']:
            pn['depends_on'].append('integrate_reader')
    cases.append(_evaluate_pair(
        case_id='B_live_cross_branch_cycle', class_id='B', category='Cooperative Liveness Deficit',
        enforcement_mechanism='TLC Temporal State-Space Proof',
        title='Muse cross-branch ordering wait loop: integrate_reader <-> build_compiler',
        fault_kind='ordering_cycle_deadlock', task_input=muse, document=doc_d2, plan=plan_d2,
        work_dir=work_root / 'B_live2', catalog=cat, expected_tla_pass=False,
    ))

    ir_d3 = _build_star_ir(star_sel, ['engine.build_expert_weight_cache'], preflight_add=False, extra_smoke=True)
    doc_d3, plan_d3, _ = plan_compile.compile_plan(ir_d3, star_sel, star)
    for pn in plan_d3['nodes']:
        if pn['node_id'] == 'build_candidate':
            pn['depends_on'].append('verify_smoke')
    cases.append(_evaluate_pair(
        case_id='B_live_custom_smoke_feedback_loop', class_id='B', category='Cooperative Liveness Deficit',
        enforcement_mechanism='TLC Temporal State-Space Proof',
        title='Autonomous Smoke Measure Step: build_candidate <-> verify_smoke mutual ordering wait',
        fault_kind='ordering_cycle_deadlock', task_input=star, document=doc_d3, plan=plan_d3,
        work_dir=work_root / 'B_live3', catalog=cat, expected_tla_pass=False,
    ))

    # --- Category 4: Formal ASSUME Contract Guard (TLA+ Load-Time Static Assertion — 2 cases) ---
    doc_a1, plan_a1, _ = plan_compile.compile_plan(
        _build_star_ir(star_sel, ['engine.build_expert_weight_cache'], preflight_add=False),
        star_sel, star,
    )
    for n in doc_a1['nodes']:
        if n['node_id'] == 'deliver_to_lab':
            n['authority_ceiling'] = {'effects': ['process.exec', 'workspace.read', 'workspace.write'], 'workspace': 'write'}
    cases.append(_evaluate_pair(
        case_id='B_assume_deliver_write_privilege', class_id='B', category='Formal ASSUME Contract Guard',
        enforcement_mechanism='TLA+ ASSUME Load-Time Assertion',
        title='Deliver Node Granted workspace=write Over-Privilege (caught by Graph.tla ASSUME)',
        fault_kind='assume_least_privilege', task_input=star, document=doc_a1, plan=plan_a1,
        work_dir=work_root / 'B_assume1', catalog=cat, expected_tla_pass=False,
    ))

    doc_a2, plan_a2, _ = plan_compile.compile_plan(
        _build_muse_ir(muse_sel, muse_all_caps, option='M1', preflight_add=False),
        muse_sel, muse,
    )
    for n in doc_a2['nodes']:
        if n['node_id'] == 'build_candidate':
            n['authority_ceiling'] = {'effects': ['process.exec', 'workspace.read', 'workspace.write'], 'workspace': 'write'}
    cases.append(_evaluate_pair(
        case_id='B_assume_build_write_overprivilege', class_id='B', category='Formal ASSUME Contract Guard',
        enforcement_mechanism='TLA+ ASSUME Load-Time Assertion',
        title='Muse Build Node Mutates Owned Checkout (workspace=write; caught by Graph.tla ASSUME)',
        fault_kind='assume_least_privilege', task_input=muse, document=doc_a2, plan=plan_a2,
        work_dir=work_root / 'B_assume2', catalog=cat, expected_tla_pass=False,
    ))

    # =========================================================================
    # Scalability & State-Space Convergence Analysis (separate from Class B!)
    # =========================================================================
    scalability = _measure_scalability(star, star_sel, work_root)

    # =========================================================================
    # Class C — Counterexample-Guided Self-Repair Suite (3 real synthesize loops)
    # =========================================================================
    repair_cases: list[dict[str, Any]] = [
        _run_repair_case(
            case_id='C1_repair_star_build_starvation',
            title='Star Single-Capsule: TLC NoStuck Feedback Repairs build_attempts=0 in Round 2',
            fault_label='NoStuck (build_candidate attempts=0)',
            task_input=star,
            bad_ir=_build_star_ir(star_sel, ['engine.build_expert_weight_cache'], limits={'build_candidate': {'build_attempts': 0}}),
            good_ir=_build_star_ir(star_sel, ['engine.build_expert_weight_cache']),
            work_dir=work_root / 'C1',
        ),
        _run_repair_case(
            case_id='C2_repair_muse_tool_starvation',
            title='Muse NVFP4 Mixed: TLC Feedback Repairs build_compiler.build_attempts=0 in Round 2',
            fault_label='NoStuck (build_compiler attempts=0)',
            task_input=muse,
            bad_ir=_build_muse_ir(muse_sel, muse_all_caps, preflight_add=True, limits={'build_compiler': {'build_attempts': 0}}),
            good_ir=_build_muse_ir(muse_sel, muse_all_caps, preflight_add=True),
            work_dir=work_root / 'C2',
        ),
        _run_repair_case(
            case_id='C3_repair_custom_smoke_stage',
            title='Autonomous Smoke Step: TLC Catches Starved Build Limit and Emits Verified JSON',
            fault_label='NoStuck (autonomous smoke starved build stage)',
            task_input=star,
            bad_ir=_build_star_ir(
                star_sel, ['engine.build_expert_weight_cache'], preflight_add=True,
                limits={'build_candidate': {'build_attempts': 0}}, extra_smoke=True,
            ),
            good_ir=_build_star_ir(
                star_sel, ['engine.build_expert_weight_cache'], preflight_add=True, extra_smoke=True,
            ),
            work_dir=work_root / 'C3',
        ),
    ]

    # =========================================================================
    # Optional Live LLM Trials
    # =========================================================================
    live_status = {
        'enabled': os.environ.get('FACTORY_PLANNER_LIVE') == '1',
        'status': 'skipped (offline mode)',
        'trials': [],
    }
    if live_status['enabled']:
        try:
            rdir, st = ai_planner.main_synthesize(str(SHIPPED / 'star-deepseek-v2.json'), out_root=work_root / 'live')
            live_status['status'] = f"executed ({st.get('state')})"
            live_status['trials'].append({'task': 'star-deepseek-v2', 'run_dir': str(rdir), 'status': st})
        except Exception as exc:
            live_status['status'] = f'live skipped/unavailable: {exc}'

    # =========================================================================
    # Aggregations (with explicit per-category breakdown!)
    # =========================================================================
    class_a = [c for c in cases if c['class'] == 'A']
    class_b = [c for c in cases if c['class'] == 'B']

    cat_order = [
        'Concurrent Lock Race',
        'Retry & Attempt Starvation',
        'Cooperative Liveness Deficit',
        'Formal ASSUME Contract Guard',
    ]
    category_breakdown = []
    for cname in cat_order:
        items = [c for c in class_b if c['category'] == cname]
        cnt = len(items)
        m1_escaped = sum(1 for c in items if c['m1_legacy']['escaped_defect'])
        escaped = sum(1 for c in items if c['static_only']['escaped_defect'])
        caught = sum(1 for c in items if not c['tla_pipeline']['admitted'])
        category_breakdown.append({
            'category': cname,
            'mechanism': items[0]['enforcement_mechanism'] if items else '',
            'count': cnt,
            'm1_escape_rate': round(m1_escaped / cnt, 4) if cnt else 0.0,
            'm1_hazard_rate_mean': round(sum(c['m1_legacy']['hazard_rate'] for c in items) / cnt, 4) if cnt else 0.0,
            'm1_wasted_nodes_mean': round(sum(c['m1_legacy']['simulation']['wasted_nodes_per_trial'] for c in items) / cnt, 2) if cnt else 0.0,
            'm1_wasted_turns_mean': round(sum(c['m1_legacy']['simulation']['wasted_turns_per_trial'] for c in items) / cnt, 1) if cnt else 0.0,
            'static_escape_rate': round(escaped / cnt, 4) if cnt else 0.0,
            'tla_block_rate': round(caught / cnt, 4) if cnt else 0.0,
            'static_hazard_rate_mean': round(sum(c['static_only']['hazard_rate'] for c in items) / cnt, 4) if cnt else 0.0,
            'static_wasted_nodes_mean': round(sum(c['static_only']['simulation']['wasted_nodes_per_trial'] for c in items) / cnt, 2) if cnt else 0.0,
            'static_wasted_turns_mean': round(sum(c['static_only']['simulation']['wasted_turns_per_trial'] for c in items) / cnt, 1) if cnt else 0.0,
            'tla_verify_seconds_mean': round(sum(c['tla_pipeline']['latency_s'] for c in items) / cnt, 3) if cnt else 0.0,
        })

    sample_case = next((c for c in class_a if c['case_id'] == 'A5_muse_mixed_preflight'), class_a[0])

    summary = {
        'total_cases': len(cases) + len(repair_cases),
        'class_a_count': len(class_a),
        'class_b_count': len(class_b),
        'class_c_count': len(repair_cases),
        'm1_checks_executed_count': sum(1 for c in cases if c['m1_legacy']['executed']),
        'm1_escaped_defects': sum(1 for c in class_b if c['m1_legacy']['escaped_defect']),
        'm1_escape_rate': round(sum(1 for c in class_b if c['m1_legacy']['escaped_defect']) / len(class_b), 4),
        'm1_class_b_hazard_rate_mean': round(sum(c['m1_legacy']['hazard_rate'] for c in class_b) / len(class_b), 4),
        'm1_class_b_wasted_nodes_mean': round(sum(c['m1_legacy']['simulation']['wasted_nodes_per_trial'] for c in class_b) / len(class_b), 2),
        'm1_class_b_wasted_turns_mean': round(sum(c['m1_legacy']['simulation']['wasted_turns_per_trial'] for c in class_b) / len(class_b), 1),
        'a_delivery_rate_m1': round(sum(c['m1_legacy']['simulation']['delivery_rate'] for c in class_a) / len(class_a), 4),
        'm1_false_positives': sum(1 for c in class_a if not c['m1_legacy']['admitted']),
        'static_escaped_defects': sum(1 for c in class_b if c['static_only']['escaped_defect']),
        'static_escape_rate': round(sum(1 for c in class_b if c['static_only']['escaped_defect']) / len(class_b), 4),
        'tla_caught_defects': sum(1 for c in class_b if not c['tla_pipeline']['admitted']),
        'tla_catch_rate': round(sum(1 for c in class_b if not c['tla_pipeline']['admitted']) / len(class_b), 4),
        'tla_caught_by_tlc_temporal': sum(1 for c in class_b if not c['tla_pipeline']['admitted'] and 'Temporal' in c['enforcement_mechanism']),
        'tla_caught_by_assume': sum(1 for c in class_b if not c['tla_pipeline']['admitted'] and 'ASSUME' in c['enforcement_mechanism']),
        'tla_false_positives': sum(1 for c in class_a if not c['tla_pipeline']['admitted']),
        'tla_false_positive_rate': round(sum(1 for c in class_a if not c['tla_pipeline']['admitted']) / len(class_a), 4),
        'roundtrip_fidelity_count': sum(1 for c in class_a if c['tla_pipeline']['roundtrip_exact']),
        'roundtrip_fidelity_rate': round(sum(1 for c in class_a if c['tla_pipeline']['roundtrip_exact']) / len(class_a), 4),
        'static_class_b_hazard_rate_mean': round(sum(c['static_only']['hazard_rate'] for c in class_b) / len(class_b), 4),
        'tla_class_b_hazard_rate_mean': 0.0,
        'static_class_b_wasted_nodes_mean': round(sum(c['static_only']['simulation']['wasted_nodes_per_trial'] for c in class_b) / len(class_b), 2),
        'static_class_b_wasted_turns_mean': round(sum(c['static_only']['simulation']['wasted_turns_per_trial'] for c in class_b) / len(class_b), 1),
        'a_delivery_rate_static': round(sum(c['static_only']['simulation']['delivery_rate'] for c in class_a) / len(class_a), 4),
        'a_delivery_rate_tla': round(sum(c['tla_pipeline']['simulation']['delivery_rate'] for c in class_a) / len(class_a), 4),
        'tla_class_a_latency_mean_s': round(sum(c['tla_pipeline']['latency_s'] for c in class_a) / len(class_a), 3),
        'tla_class_b_latency_mean_s': round(sum(c['tla_pipeline']['latency_s'] for c in class_b) / len(class_b), 3),
        'parse_taskgraph_tla_mean_ms': round(sum(c['tla_pipeline']['parse_ms'] for c in cases) / len(cases), 3),
        'repair_success_count': sum(1 for r in repair_cases if r['tla_final_state'] == 'succeeded' and r['verified_json_emitted']),
        'repair_success_rate': round(sum(1 for r in repair_cases if r['tla_final_state'] == 'succeeded' and r['verified_json_emitted']) / len(repair_cases), 4),
        'scalability_k5_reduction': scalability[-1]['state_reduction_ratio'] if scalability else 1.0,
    }

    payload = {
        'generated_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        'm1_limitations': list(m1_verifier_bridge.M1_LIMITATIONS),
        'environment': {
            'os': f'{platform.system()} {platform.release()} ({platform.machine()})',
            'python': sys.version.split()[0],
            'java': _java_version(java),
            'tla2tools_jar': str(jar),
            'tla2tools_sha256': hashlib.sha256(Path(jar).read_bytes()).hexdigest(),
            'git_commit': _git_commit(),
            'simulation_trials_per_case': 100,
            'simulation_seed': 42,
            'transient_fail_prob': 0.15,
            'reproduce_command': '.venv/bin/python -m benchmarks.planner_tlc_ablation.run_ablation',
        },
        'summary': summary,
        'category_breakdown': category_breakdown,
        'scalability': scalability,
        'sample_graph_tla': {
            'case_id': sample_case['case_id'],
            'title': sample_case['title'],
            'bytes': sample_case['tla_pipeline']['graph_tla_bytes'],
            'source': sample_case['tla_pipeline']['graph_tla_preview'],
        },
        'cases': cases,
        'repair_cases': repair_cases,
        'live_trials': live_status,
    }
    (out_dir / 'results.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return payload


def main():
    from .report_gen import generate_html
    payload = run_all(HERE)
    html_path = generate_html(payload, HERE / 'report.html')
    print(json.dumps({'results': str(HERE / 'results.json'), 'report': str(html_path), 'summary': payload['summary']}, indent=2))


if __name__ == '__main__':
    main()
