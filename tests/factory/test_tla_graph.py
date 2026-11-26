"""Tests for standalone ``graph.tla`` deliverable, TLC ASSUME/NoStuck verification,
zero-JVM pure-Python ``parse_taskgraph_tla`` / ``load_taskgraph``, and downstream seeding.
"""
from __future__ import annotations

import asyncio
import copy
import json
import subprocess
from pathlib import Path

from fastapi import FastAPI
from starlette.testclient import TestClient

from jiuwenswarm.factory import (
    ai_planner,
    cli,
    controller,
    node_contract,
    plan_compile,
    plan_select,
    requirements as req,
    scheduler,
    tla_check,
    tla_graph,
)
from jiuwenswarm.factory.store import Store
from jiuwenswarm.factory.tla_graph import load_taskgraph, parse_taskgraph_tla
from jiuwenswarm.gateway.channel_manager.web import factory_planner_http

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED = REPO_ROOT / 'jiuwenswarm' / 'factory' / 'requirements'


def test_standalone_graph_tla_runs_in_empty_directory_with_tlc(tmp_path):
    """Copy ONLY graph.tla into an otherwise empty dir and run java tlc2.TLC directly."""
    muse = req.load(SHIPPED / 'muse-q2-ttft-v2.json')
    sel = plan_select.context(muse)
    ir = {
        'format': 'factory.plan-ir/1',
        'selected_capsules': [
            {'capsule': 'weights.build_muse_nvfp4_reader', 'why': 'reader'},
            {'capsule': 'weights.build_expert_scale_wiring', 'why': 'wiring'},
            {'capsule': 'weights.build_weight_pack_compiler', 'why': 'compiler'},
            {'capsule': 'engine.build_expert_weight_cache', 'why': 'cache'},
        ],
        'preflight': [{'unit': 'cache', 'add': True, 'why': 'sm_87 vs sm_121'}],
        'merge': {'option': 'M1', 'why': 'merge converter, wiring and cache'},
        'steps': [
            {'id': 'inspect_engine', 'kind': 'inspect', 'objective': 'Inspect checkout.',
             'depends_on': [], 'capsules': ['factory.engine_inspector']},
            {'id': 'preflight_cache', 'kind': 'inspect', 'objective': 'Check cache applicability.',
             'depends_on': ['inspect_engine'], 'capsules': ['engine.build_expert_weight_cache']},
            {'id': 'integrate_reader', 'kind': 'integrate', 'objective': 'Integrate reader.',
             'depends_on': ['inspect_engine'], 'capsules': ['weights.build_muse_nvfp4_reader']},
            {'id': 'integrate_wiring', 'kind': 'integrate', 'objective': 'Integrate wiring.',
             'depends_on': ['inspect_engine'], 'capsules': ['weights.build_expert_scale_wiring']},
            {'id': 'integrate_cache', 'kind': 'integrate', 'objective': 'Integrate cache.',
             'depends_on': ['preflight_cache'], 'capsules': ['engine.build_expert_weight_cache']},
            {'id': 'build_compiler', 'kind': 'build', 'objective': 'Compile pack.',
             'depends_on': ['inspect_engine', 'integrate_reader'], 'capsules': ['weights.build_weight_pack_compiler']},
            {'id': 'combine', 'kind': 'merge', 'objective': 'Combine diffs.',
             'depends_on': ['integrate_reader', 'integrate_wiring', 'integrate_cache'],
             'capsules': ['factory.integration_skill']},
            {'id': 'build_candidate', 'kind': 'build', 'objective': 'Build bundle.',
             'depends_on': ['combine', 'build_compiler'], 'capsules': ['factory.builder']},
            {'id': 'deliver_to_lab', 'kind': 'deliver', 'objective': 'Deliver to lab.',
             'depends_on': ['build_candidate'], 'capsules': ['factory.lab_manager']},
        ],
    }
    tla_text, doc, plan, _ = plan_compile.compile_to_tla(ir, sel, muse)

    isolated = tmp_path / 'blank_dir'
    isolated.mkdir()
    (isolated / 'Graph.tla').write_text(tla_text, encoding='utf-8')
    assert sorted(p.name for p in isolated.iterdir()) == ['Graph.tla']

    java, jar = tla_check.tools()
    for run_name, coop, invs in tla_check.RUNS:
        (isolated / f'{run_name}.cfg').write_text(tla_check.standalone_config(coop, invs), encoding='utf-8')
        proc = subprocess.run(
            [java, '-XX:+UseParallelGC', '-cp', str(jar), 'tlc2.TLC', '-cleanup', '-config', f'{run_name}.cfg', 'Graph.tla'],
            cwd=isolated,
            capture_output=True,
            text=True,
            check=False,
        )
        out = proc.stdout + proc.stderr
        assert 'Model checking completed. No error has been found.' in out, (run_name, out[-1500:])


def test_graph_tla_tlc_catches_injected_assume_and_liveness_defects(tmp_path):
    star = req.load(SHIPPED / 'star-deepseek-v2.json')
    sel = plan_select.context(star)
    ir = {
        'format': 'factory.plan-ir/1',
        'selected_capsules': [{'capsule': 'engine.build_expert_weight_cache', 'why': 'cache'}],
        'preflight': [{'unit': 'cache', 'add': False, 'why': 'skip'}],
        'steps': [
            {'id': 'inspect_engine', 'kind': 'inspect', 'objective': 'Inspect checkout.',
             'depends_on': [], 'capsules': ['factory.engine_inspector']},
            {'id': 'integrate_cache', 'kind': 'integrate', 'objective': 'Integrate cache.',
             'depends_on': ['inspect_engine'], 'capsules': ['engine.build_expert_weight_cache']},
            {'id': 'build_candidate', 'kind': 'build', 'objective': 'Build bundle.',
             'depends_on': ['integrate_cache'], 'capsules': ['factory.builder']},
            {'id': 'deliver_to_lab', 'kind': 'deliver', 'objective': 'Deliver to lab.',
             'depends_on': ['build_candidate'], 'capsules': ['factory.lab_manager']},
        ],
    }
    doc, plan, _ = plan_compile.compile_plan(ir, sel, star)

    # 1. Inject build_attempts = 0 -> TLC catches NoStuck deadlock
    bad_build = copy.deepcopy(doc)
    for n in bad_build['nodes']:
        if n['node_id'] == 'build_candidate':
            n['node_limits']['build_attempts'] = 0
    v_stuck = tla_check.check_graph_tla(tla_graph.render_graph_tla(bad_build, star, plan), tmp_path / 'stuck')
    assert not v_stuck['passed']
    assert any('NoStuck' in p for p in v_stuck['problems'])

    # 2. Inject unauthorized effect -> TLC catches ASSUME violation at load time
    bad_eff = copy.deepcopy(doc)
    bad_eff['nodes'][0]['authority_ceiling']['effects'].append('gpu.use')
    v_eff = tla_check.check_graph_tla(tla_graph.render_graph_tla(bad_eff, star, plan), tmp_path / 'eff')
    assert not v_eff['passed']
    assert any('ASSUME' in p or 'Assertion' in p or 'assertion' in p for p in v_eff['problems'])

    # 3. Inject diff output on read-only node -> TLC catches ASSUME violation
    bad_ws = copy.deepcopy(doc)
    for n in bad_ws['nodes']:
        if n['node_id'] == 'integrate_cache':
            n['authority_ceiling']['workspace'] = 'read'
    v_ws = tla_check.check_graph_tla(tla_graph.render_graph_tla(bad_ws, star, plan), tmp_path / 'ws')
    assert not v_ws['passed']
    assert any('ASSUME' in p or 'assertion' in p for p in v_ws['problems'])


def test_lossless_roundtrip_special_chars_and_zero_jvm_parser(tmp_path, monkeypatch):
    star = req.load(SHIPPED / 'star-deepseek-v2.json')
    sel = plan_select.context(star)
    caps = [
        'engine.build_expert_weight_cache',
        'routing.build_expert_demand_predictor',
        'engine.build_batch_layout_mapper',
    ]
    risky_units = [c['unit'] for c in sel['candidates'] if c['capsule'] in caps and any(r['capsule'] == c['capsule'] for r in sel['risks'])]
    ir = {
        'format': 'factory.plan-ir/1',
        'selected_capsules': [{'capsule': c, 'why': 'selected'} for c in caps],
        'preflight': [{'unit': u, 'add': u == 'cache', 'why': 'sm_87 vs sm_121'} for u in risky_units],
        'merge': {'option': 'M2' if 'M2' in sel['merge_options'] else 'M1', 'why': 'cluster merge'},
        'steps': [
            {'id': 'inspect_engine', 'kind': 'inspect', 'objective': 'Inspect checkout.',
             'depends_on': [], 'capsules': ['factory.engine_inspector']},
            {'id': 'preflight_cache', 'kind': 'inspect', 'objective': 'Check cache applicability.',
             'depends_on': ['inspect_engine'], 'capsules': ['engine.build_expert_weight_cache']},
            {'id': 'integrate_cache', 'kind': 'integrate', 'objective': 'Integrate cache.',
             'depends_on': ['preflight_cache'], 'capsules': ['engine.build_expert_weight_cache']},
            {'id': 'integrate_predictor', 'kind': 'integrate', 'objective': 'Integrate predictor.',
             'depends_on': ['inspect_engine'], 'capsules': ['routing.build_expert_demand_predictor']},
            {'id': 'integrate_mapper', 'kind': 'integrate', 'objective': 'Integrate mapper.',
             'depends_on': ['inspect_engine'], 'capsules': ['engine.build_batch_layout_mapper']},
            {'id': 'combine', 'kind': 'merge', 'objective': 'Combine diffs.',
             'depends_on': ['integrate_cache', 'integrate_predictor', 'integrate_mapper'],
             'capsules': ['factory.integration_skill']},
            {'id': 'build_candidate', 'kind': 'build', 'objective': 'Build bundle.',
             'depends_on': ['combine'], 'capsules': ['factory.builder']},
            {'id': 'deliver_to_lab', 'kind': 'deliver', 'objective': 'Deliver to lab.',
             'depends_on': ['build_candidate'], 'capsules': ['factory.lab_manager']},
        ],
    }
    doc, plan, _ = plan_compile.compile_plan(ir, sel, star)
    # Inject special characters into objective & criteria
    doc['nodes'][0]['objective'] = 'Check "quotes", path\\seg, tab\tand\nnewline (DGX Spark GB10).'
    doc['nodes'][1]['outputs'][0]['criteria'].append('Escaped "value" \\ line\ncheck.')

    tla_path = tmp_path / 'graph.tla'
    tla_path.write_text(tla_graph.render_graph_tla(doc, star, plan), encoding='utf-8')

    # Verify ZERO JVM / subprocess invocation when parsing!
    def _forbid(*_args, **_kwargs):
        raise AssertionError('JVM / TLC tools must never be called by parse_taskgraph_tla or load_taskgraph')

    monkeypatch.setattr(tla_check, 'tools', _forbid)
    monkeypatch.setattr(subprocess, 'run', _forbid)

    parsed = load_taskgraph(tla_path)
    assert set(['task_id', 'objective', 'nodes', 'node_contracts', 'plan', 'execution_model']) <= set(parsed)
    assert parsed['node_contracts'] == doc
    assert parsed['nodes'] == doc['nodes']
    assert parsed['plan'] == plan
    assert parsed['task_id'] == 'star-deepseek-v2'
    assert 'DGX Spark' in parsed['objective']
    assert 'DGX Spark GB10' in parsed['nodes'][0]['objective']
    assert '"quotes"' in parsed['nodes'][0]['objective']
    assert 'tab\tand\nnewline' in parsed['nodes'][0]['objective']
    assert node_contract.problems(parsed['node_contracts']) == []


def test_end_to_end_synthesize_outputs_verified_json_with_internal_tlc_and_downstream_consumes(tmp_path, capsys):
    """Both star-deepseek-v2 and muse-q2-ttft-v2 use TLC internally and emit verified JSON -> init/seed_plan/scheduler/HTTP/CLI."""
    muse = req.load(SHIPPED / 'muse-q2-ttft-v2.json')
    ir_reply = json.dumps({
        'format': 'factory.plan-ir/1',
        'selected_capsules': [
            {'capsule': 'weights.build_muse_nvfp4_reader', 'why': 'reader'},
            {'capsule': 'weights.build_expert_scale_wiring', 'why': 'wiring'},
            {'capsule': 'weights.build_weight_pack_compiler', 'why': 'compiler'},
            {'capsule': 'engine.build_expert_weight_cache', 'why': 'cache'},
        ],
        'preflight': [{'unit': 'cache', 'add': True, 'why': 'sm_87 vs sm_121'}],
        'merge': {'option': 'M1', 'why': 'combine diffs'},
        'steps': [
            {'id': 'inspect_engine', 'kind': 'inspect', 'objective': 'Inspect checkout.',
             'depends_on': [], 'capsules': ['factory.engine_inspector']},
            {'id': 'preflight_cache', 'kind': 'inspect', 'objective': 'Check cache applicability.',
             'depends_on': ['inspect_engine'], 'capsules': ['engine.build_expert_weight_cache']},
            {'id': 'integrate_reader', 'kind': 'integrate', 'objective': 'Integrate reader.',
             'depends_on': ['inspect_engine'], 'capsules': ['weights.build_muse_nvfp4_reader']},
            {'id': 'integrate_wiring', 'kind': 'integrate', 'objective': 'Integrate wiring.',
             'depends_on': ['inspect_engine'], 'capsules': ['weights.build_expert_scale_wiring']},
            {'id': 'integrate_cache', 'kind': 'integrate', 'objective': 'Integrate cache.',
             'depends_on': ['preflight_cache'], 'capsules': ['engine.build_expert_weight_cache']},
            {'id': 'build_compiler', 'kind': 'build', 'objective': 'Compile pack.',
             'depends_on': ['inspect_engine', 'integrate_reader'], 'capsules': ['weights.build_weight_pack_compiler']},
            {'id': 'combine', 'kind': 'merge', 'objective': 'Combine diffs.',
             'depends_on': ['integrate_reader', 'integrate_wiring', 'integrate_cache'],
             'capsules': ['factory.integration_skill']},
            {'id': 'build_candidate', 'kind': 'build', 'objective': 'Build bundle.',
             'depends_on': ['combine', 'build_compiler'], 'capsules': ['factory.builder']},
            {'id': 'deliver_to_lab', 'kind': 'deliver', 'objective': 'Deliver to lab.',
             'depends_on': ['build_candidate'], 'capsules': ['factory.lab_manager']},
        ],
    })

    async def fake_invoke(prompt, system):
        return {'text': ir_reply, 'identity': 'fake-muse'}

    run_dir = tmp_path / 'plans' / ai_planner.new_plan_id()
    status = asyncio.run(ai_planner.synthesize(muse, run_dir, invoke=fake_invoke))
    assert status['state'] == 'succeeded'

    # External deliverable check: standard verified JSON files, NO top-level graph.tla
    assert not (run_dir / 'graph.tla').exists()
    for present in ('contract.json', 'plan.json', 'graph.json', 'verification.json', 'task.json'):
        assert (run_dir / present).is_file(), f'{present} should exist as verified JSON deliverable'
    rec = json.loads((run_dir / 'plan-record.json').read_text(encoding='utf-8'))
    assert {'contract.json', 'plan.json', 'graph.json', 'verification.json', 'task.json'} == set(rec['outputs'])

    # Direct controller.init_task(task.json) -> contract.json + plan.json -> scheduler.next_work!
    ctrl = controller.Controller(tmp_path / 'factory-home')
    try:
        tid = ctrl.init_task(run_dir / 'task.json')
        work = scheduler.next_work(ctrl.store, tid)
        assert work['schema'] == 'factory.next-work/1'
        assert [r['node_id'] for r in work['runnable']] == ['inspect_engine']
        assert 'preflight_cache' in work['waiting']
        assert work['runnable'][0]['limits_left']['turns'] == 10
    finally:
        ctrl.store.close()

    # Replay check compares generated contract.json + plan.json
    verdicts = ai_planner.replay(run_dir)
    assert verdicts[0]['passed'] and verdicts[0]['same'] and verdicts[0]['same_graph']

    # CLI verify-plan directly on verified contract.json
    from argparse import Namespace
    exit_code = cli.verify_plan_command(Namespace(
        contract=str(run_dir / 'contract.json'),
        requirements=str(SHIPPED / 'muse-q2-ttft-v2.json'),
        max_parallel=None,
        attempts=None,
        out=str(tmp_path / 'cli-verify'),
    ))
    assert exit_code == 0
    verify_json = json.loads(capsys.readouterr().out)
    assert verify_json['static']['problems'] == [] and verify_json['tla']['passed']

    # HTTP detail returns verified JSON outputs cleanly (no graph.tla required)
    app = FastAPI()
    svc = factory_planner_http.FactoryPlannerService(root=tmp_path / 'plans')
    factory_planner_http.attach_planner_routes(app, service=svc)
    client = TestClient(app)
    detail_resp = client.get(f'/api/factory/planner/runs/{run_dir.name}')
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert {'contract.json', 'plan.json', 'graph.json', 'verification.json', 'task.json'} <= set(body['outputs'])
    assert body['graph']['nodes'] and body['node_contracts']['nodes']
    assert client.get(f'/api/factory/planner/runs/{run_dir.name}/graph.tla').status_code == 404
