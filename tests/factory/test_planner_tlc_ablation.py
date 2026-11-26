"""Unit tests for the Planner TLC ablation simulator, JS syntax, DOM rendering, and HTML report."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from benchmarks.planner_tlc_ablation.report_gen import generate_html
from benchmarks.planner_tlc_ablation.simulator import simulate_graph
from jiuwenswarm.factory import plan_compile, plan_select, requirements as req, tla_check

SHIPPED = Path(__file__).resolve().parents[2] / 'jiuwenswarm' / 'factory' / 'requirements'


def test_simulator_is_deterministic_and_catches_starvation_and_races():
    star = req.load(SHIPPED / 'star-deepseek-v2.json')
    sel = plan_select.context(star)
    ir = {
        'format': 'factory.plan-ir/1',
        'selected_capsules': [{'capsule': 'engine.build_expert_weight_cache', 'why': 'cache'}],
        'preflight': [{'unit': 'cache', 'add': True, 'why': 'sm_87 vs sm_121'}],
        'steps': [
            {'id': 'inspect_engine', 'kind': 'inspect', 'objective': 'Inspect checkout.',
             'depends_on': [], 'capsules': ['factory.engine_inspector']},
            {'id': 'preflight_cache', 'kind': 'inspect', 'objective': 'Check cache applicability.',
             'depends_on': ['inspect_engine'], 'capsules': ['engine.build_expert_weight_cache']},
            {'id': 'integrate_cache', 'kind': 'integrate', 'objective': 'Integrate cache.',
             'depends_on': ['preflight_cache'], 'capsules': ['engine.build_expert_weight_cache']},
            {'id': 'build_candidate', 'kind': 'build', 'objective': 'Build bundle.',
             'depends_on': ['integrate_cache'], 'capsules': ['factory.builder']},
            {'id': 'deliver_to_lab', 'kind': 'deliver', 'objective': 'Deliver to lab.',
             'depends_on': ['build_candidate'], 'capsules': ['factory.lab_manager']},
        ],
    }
    doc, plan, _ = plan_compile.compile_plan(ir, sel, star)
    allowed = star['constraints']['allowed_effects']
    model = tla_check.execution_model(doc)

    sim1 = simulate_graph(doc, model, allowed, trials=40, seed=42)
    sim2 = simulate_graph(doc, model, allowed, trials=40, seed=42)
    assert sim1 == sim2
    assert sim1['delivery_rate'] >= 0.90
    assert sim1['contract_violation_rate'] == 0.0

    # Inject build_attempts = 0 starvation -> 100% stuck & wasted upstream work > 0
    starved = {**doc, 'nodes': [dict(n) for n in doc['nodes']]}
    for n in starved['nodes']:
        if n['node_id'] == 'build_candidate':
            n['node_limits'] = {'turns': 15, 'build_attempts': 0}
    starved_sim = simulate_graph(starved, tla_check.execution_model(starved), allowed, trials=40, seed=42)
    assert starved_sim['stuck_rate'] == 1.0
    assert starved_sim['wasted_nodes_per_trial'] >= 3.0
    assert starved_sim['wasted_turns_per_trial'] > 0.0

    # Inject concurrent writer race when checkout lock is missing on parallel writers
    multi_ir = {
        'format': 'factory.plan-ir/1',
        'selected_capsules': [
            {'capsule': 'observability.build_runtime_event_recorder', 'why': 'rec'},
            {'capsule': 'engine.build_expert_weight_cache', 'why': 'cache'},
        ],
        'preflight': [
            {'unit': 'cache', 'add': False, 'why': 'skip'},
            {'unit': 'recorder', 'add': False, 'why': 'skip'},
        ],
        'merge': {'option': 'M1', 'why': 'm1'},
        'steps': [
            {'id': 'inspect_engine', 'kind': 'inspect', 'objective': 'Inspect checkout.',
             'depends_on': [], 'capsules': ['factory.engine_inspector']},
            {'id': 'integrate_recorder', 'kind': 'integrate', 'objective': 'Integrate recorder.',
             'depends_on': ['inspect_engine'], 'capsules': ['observability.build_runtime_event_recorder']},
            {'id': 'integrate_cache', 'kind': 'integrate', 'objective': 'Integrate cache.',
             'depends_on': ['inspect_engine'], 'capsules': ['engine.build_expert_weight_cache']},
            {'id': 'combine', 'kind': 'merge', 'objective': 'Merge diffs.',
             'depends_on': ['integrate_recorder', 'integrate_cache'], 'capsules': ['factory.integration_skill']},
            {'id': 'build_candidate', 'kind': 'build', 'objective': 'Build bundle.',
             'depends_on': ['combine'], 'capsules': ['factory.builder']},
            {'id': 'deliver_to_lab', 'kind': 'deliver', 'objective': 'Deliver to lab.',
             'depends_on': ['build_candidate'], 'capsules': ['factory.lab_manager']},
        ],
    }
    mdoc, _, _ = plan_compile.compile_plan(multi_ir, sel, star)
    m_model = tla_check.execution_model(mdoc)
    m_model['exclusive']['integrate_cache'] = []
    m_model['exclusive']['integrate_recorder'] = []
    race_sim = simulate_graph(mdoc, m_model, allowed, trials=40, seed=42)
    assert race_sim['contract_violation_rate'] > 0.5
    assert race_sim['race_violations'] > 0


def _dummy_payload():
    return {
        'generated_at': '2026-11-25T16:40:00Z',
        'environment': {
            'os': 'macOS arm64', 'python': '3.13.0', 'java': 'openjdk',
            'tla2tools_jar': 'tla2tools.jar', 'tla2tools_sha256': 'abc',
            'git_commit': 'deadbeef', 'simulation_trials_per_case': 100,
            'simulation_seed': 42, 'transient_fail_prob': 0.15,
            'reproduce_command': '.venv/bin/python -m benchmarks.planner_tlc_ablation.run_ablation',
        },
        'm1_limitations': [{
            'id': 'm1_single_attempt_no_starvation',
            'title': 'Single-attempt lock',
            'summary': 'M1 locks max_attempts_per_node == 1.',
            'source_refs': ['jiuwenswarm/research/binding.py:98'],
        }],
        'summary': {
            'total_cases': 2, 'class_a_count': 1, 'class_b_count': 1, 'class_c_count': 0,
            'm1_checks_executed_count': 2, 'm1_escaped_defects': 1, 'm1_escape_rate': 1.0,
            'm1_class_b_hazard_rate_mean': 1.0, 'm1_class_b_wasted_nodes_mean': 3.0,
            'm1_class_b_wasted_turns_mean': 70.0, 'a_delivery_rate_m1': 0.85, 'm1_false_positives': 0,
            'static_escaped_defects': 1, 'static_escape_rate': 1.0,
            'tla_caught_defects': 1, 'tla_catch_rate': 1.0,
            'tla_caught_by_tlc_temporal': 1, 'tla_caught_by_assume': 0,
            'tla_false_positives': 0, 'tla_false_positive_rate': 0.0,
            'roundtrip_fidelity_count': 1, 'roundtrip_fidelity_rate': 1.0,
            'static_class_b_hazard_rate_mean': 1.0, 'tla_class_b_hazard_rate_mean': 0.0,
            'static_class_b_wasted_nodes_mean': 3.0, 'static_class_b_wasted_turns_mean': 70.0,
            'a_delivery_rate_static': 1.0, 'a_delivery_rate_tla': 1.0,
            'tla_class_a_latency_mean_s': 0.8, 'tla_class_b_latency_mean_s': 0.5,
            'parse_taskgraph_tla_mean_ms': 1.2,
            'repair_success_count': 0, 'repair_success_rate': 1.0,
            'scalability_k5_reduction': 4.24,
        },
        'category_breakdown': [{
            'category': 'Concurrent Lock Race', 'mechanism': 'TLC Temporal State-Space Proof',
            'count': 1, 'm1_escape_rate': 1.0, 'm1_hazard_rate_mean': 1.0,
            'm1_wasted_nodes_mean': 3.0, 'm1_wasted_turns_mean': 70.0,
            'static_escape_rate': 1.0, 'tla_block_rate': 1.0,
            'static_hazard_rate_mean': 1.0, 'static_wasted_nodes_mean': 3.0,
            'static_wasted_turns_mean': 70.0, 'tla_verify_seconds_mean': 0.5,
        }],
        'scalability': [
            {'k': 2, 'unconstrained_states': 1051, 'unconstrained_seconds': 1.0, 'unconstrained_passed': True,
             'ordered_states': 967, 'ordered_seconds': 0.7, 'ordered_passed': True, 'state_reduction_ratio': 1.09},
            {'k': 5, 'unconstrained_states': 33031, 'unconstrained_seconds': 1.6, 'unconstrained_passed': True,
             'ordered_states': 7799, 'ordered_seconds': 1.0, 'ordered_passed': True, 'state_reduction_ratio': 4.24},
        ],
        'sample_graph_tla': {'case_id': 'A1', 'title': 'Sample', 'bytes': 120, 'source': '-- 1.\nNodes == {"a"}\n-- 2.\n-- 3.\n-- 4.'},
        'cases': [{
            'case_id': 'A1', 'class': 'A', 'category': 'Healthy Baseline',
            'enforcement_mechanism': 'TLC Temporal State-Space Proof', 'title': 'Healthy',
            'fault_kind': None, 'node_count': 4, 'task_id': 'star-deepseek-v2', 'expected_tla_pass': True,
            'm1_legacy': {'executed': True, 'admitted': True, 'escaped_defect': False, 'hazard_rate': 0.15,
                          'simulation': {'delivered': 85, 'stuck_or_failed': 15, 'delivery_rate': 0.85, 'stuck_rate': 0.15,
                                         'race_violations': 0, 'authority_violations': 0, 'wasted_nodes_per_trial': 0.2,
                                         'wasted_turns_per_trial': 4.0, 'failure_reasons': {'attempt_exhaustion_failure': 15}}},
            'static_only': {'static_problems': [], 'warnings': [], 'admitted': True, 'escaped_defect': False,
                            'latency_s': 0.01, 'hazard_rate': 0.0,
                            'simulation': {'delivered': 100, 'stuck_or_failed': 0, 'delivery_rate': 1.0, 'stuck_rate': 0.0,
                                           'race_violations': 0, 'authority_violations': 0, 'wasted_nodes_per_trial': 0.0,
                                           'wasted_turns_per_trial': 0.0, 'failure_reasons': {}}},
            'tla_pipeline': {'admitted': True, 'tlc_passed': True, 'tlc_problems': [],
                             'runs': [{'run': 'safety', 'passed': True, 'distinct_states': 100, 'seconds': 0.3}],
                             'total_distinct_states': 100, 'total_states_generated': 120,
                             'latency_s': 0.6, 'parse_ms': 1.2, 'roundtrip_exact': True, 'graph_tla_bytes': 120,
                             'counterexample_trace': [], 'simulation': {'delivery_rate': 1.0}},
        }],
        'repair_cases': [{
            'case_id': 'C1', 'class': 'C', 'title': 'Repair Test', 'fault_label': 'NoStuck',
            'static_round1_problems': [], 'static_admitted_buggy_round1': True,
            'static_round1_simulation': {'delivery_rate': 0.0, 'wasted_turns_per_trial': 60.0},
            'tla_final_state': 'succeeded', 'tla_rounds_taken': 2, 'tla_total_latency_s': 1.2,
            'verified_json_emitted': True, 'round1_layer': 'tla', 'round1_problems': ['NoStuck'],
            'round1_trace': [{'state': 1, 'action': 'Init', 'st': {'a': 'waiting'}, 'att': {'a': 0}}],
            'feedback_excerpt': 'Fix build_attempts', 'changed_ir_fields': ['limits'],
            'tla_final_simulation': {'delivery_rate': 1.0},
        }],
        'live_trials': {'enabled': False, 'status': 'skipped (offline mode)', 'trials': []},
    }


def _assert_valid_report_html(html_path: Path):
    text = html_path.read_text(encoding='utf-8')
    assert '<!DOCTYPE html>' in text
    assert '__DATA_JSON__' not in text
    assert 'src="http' not in text and 'href="http' not in text
    # Strictly forbid internal codenames B0 / T1 in user-facing HTML
    assert not re.search(r'\bB0\b|\bT1\b', text), 'Found forbidden internal codename B0 or T1 in report.html'

    # Extract <script> block and validate JS syntax with Node + verify real DOM rendering!
    match = re.search(r'<script>\n([\s\S]*?)\n</script>', text)
    assert match, 'Missing inline <script> block'
    js_code = match.group(1)
    # Strip `const DATA = ...;` JSON payload line before verifying no raw newline in .split/.join literals
    js_logic = js_code.split('\n', 1)[1] if js_code.startswith('const DATA = ') else js_code
    assert "'\\n'" in js_logic
    assert not re.search(r"(?:split|join)\('\n'\)", js_logic), 'Raw unescaped newline inside single-quoted JS string!'

    node_bin = shutil.which('node')
    assert node_bin, 'node executable required to syntax-check report.html JavaScript'
    js_tmp = html_path.with_suffix('.extracted.js')
    js_tmp.write_text(js_code, encoding='utf-8')
    chk = subprocess.run([node_bin, '--check', str(js_tmp)], capture_output=True, text=True, check=False)
    assert chk.returncode == 0, f'node --check failed:\n{chk.stderr}'

    # Execute the extracted JS against a minimal mock DOM in Node to guarantee zero runtime errors and non-empty renders!
    harness = f"""
    const fs = require('fs');
    const vm = require('vm');
    const elements = {{}};
    function makeEl(id) {{
      return {{
        id, innerHTML: '', textContent: '', dataset: {{}},
        attrs: {{}},
        classList: {{ toggle() {{}}, add() {{}}, remove() {{}} }},
        setAttribute(k, v) {{ this.attrs[k] = v; }},
        getAttribute(k) {{ return this.attrs[k] || 'light'; }},
        addEventListener() {{}},
        querySelectorAll() {{ return []; }},
        scrollIntoView() {{}},
        value: '',
      }};
    }}
    const document = {{
      documentElement: makeEl('html'),
      getElementById(id) {{ return (elements[id] ||= makeEl(id)); }},
      querySelectorAll(sel) {{
        return [makeEl('q1')];
      }},
    }};
    const navigator = {{ clipboard: {{ writeText() {{}} }} }};
    const code = fs.readFileSync({json.dumps(str(js_tmp))}, 'utf8');
    vm.runInNewContext(code, {{ document, navigator, setTimeout: () => {{}}, console }});
    const requiredIds = ['kpi-grid', 'm1-gaps-list', 'category-tbody', 'env-table', 'chart-escape', 'chart-waste', 'chart-scale', 'chart-healthy', 'tla-inspector', 'cases-tbody', 'repair-container'];
    for (const id of requiredIds) {{
      if (!elements[id] || !elements[id].innerHTML || elements[id].innerHTML.trim().length < 20) {{
        throw new Error('DOM container rendered empty: ' + id);
      }}
    }}
    console.log('DOM_RENDER_OK');
    """
    dom_run = subprocess.run([node_bin, '-e', harness], capture_output=True, text=True, check=False)
    js_tmp.unlink(missing_ok=True)
    assert dom_run.returncode == 0 and 'DOM_RENDER_OK' in dom_run.stdout, (dom_run.stdout, dom_run.stderr)


def test_report_generator_js_syntax_and_dom_rendering(tmp_path):
    out = generate_html(_dummy_payload(), tmp_path / 'report.html')
    _assert_valid_report_html(out)


def test_real_ablation_artifacts_and_http_endpoints():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from jiuwenswarm.gateway.channel_manager.web import factory_planner_http

    ablation_dir = Path(__file__).resolve().parents[2] / 'benchmarks' / 'planner_tlc_ablation'
    results_path = ablation_dir / 'results.json'
    report_path = ablation_dir / 'report.html'
    assert results_path.is_file() and report_path.is_file()

    payload = json.loads(results_path.read_text(encoding='utf-8'))
    s = payload['summary']
    assert s['m1_checks_executed_count'] == 16
    assert s['m1_escape_rate'] == 1.0
    assert s['static_escape_rate'] == 1.0
    assert s['tla_catch_rate'] == 1.0
    assert s['tla_false_positive_rate'] == 0.0
    assert s['a_delivery_rate_m1'] < s['a_delivery_rate_tla'] == 1.0
    assert s['repair_success_rate'] == 1.0
    assert all(r['verified_json_emitted'] for r in payload['repair_cases'])
    assert len(payload.get('m1_limitations', [])) == 4

    _assert_valid_report_html(report_path)
    report_text = report_path.read_text(encoding='utf-8')
    assert 'Experimental Setup: What Are the Inputs, Baselines &amp; Fairness Rules?' in report_text
    assert 'Baseline 1 — Old M1' in report_text
    assert 'Baseline 2 — M2 Static-Only' in report_text
    assert 'Fairness Contract' in report_text

    from benchmarks.planner_tlc_ablation.build_onepager_zh import build_pdf
    pdf_path = build_pdf(results_path=results_path, pdf_path=ablation_dir / 'tlc_architecture_onepager_zh.pdf')
    assert pdf_path.is_file()
    info = subprocess.run(['pdfinfo', str(pdf_path)], capture_output=True, text=True, check=True)
    assert any(line.strip() == 'Pages:\t1' or line.replace(' ', '') == 'Pages:1' for line in info.stdout.splitlines())

    app = FastAPI()
    svc = factory_planner_http.FactoryPlannerService(ablation_dir=ablation_dir)
    factory_planner_http.attach_planner_routes(app, service=svc)
    client = TestClient(app)
    r_json = client.get('/api/factory/planner/ablation')
    assert r_json.status_code == 200
    assert r_json.json()['report_available'] is True
    r_html = client.get('/api/factory/planner/ablation/report.html')
    assert r_html.status_code == 200 and 'Old M1' in r_html.text and 'M2 Static' in r_html.text
