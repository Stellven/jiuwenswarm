"""The AI planner: single self-contained TaskInput in, proven single-solution TaskGraph out.

Tests cover TaskInput validation, capsule selection & hard/soft filtering, Plan IR
boundaries, single-capsule (no merge) & multi-capsule (M1/M2/M3) compilation,
acceptance_criteria binding, static checks, multi-round feedback + replay, init gate,
and HTTP routes.
"""
import asyncio
import copy
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from jiuwenswarm.factory import ai_planner, plan_catalog, plan_checks, plan_compile, plan_ir, plan_select, requirements as req, tla_check
from jiuwenswarm.factory.planner import contract_plan
from jiuwenswarm.factory.taskgraph import seed_plan

REPO = Path(__file__).resolve().parents[2]
STAR_INPUT = REPO / 'jiuwenswarm/factory/requirements/star-deepseek-v2.json'
MUSE_INPUT = REPO / 'jiuwenswarm/factory/requirements/muse-q2-ttft-v2.json'


def nodes_of(document):
    return {n['node_id']: n for n in document['nodes']}


def standalone_task_input():
    return {
        'format': 'factory.task-input/1',
        'task_id': 'spark-cache-only',
        'objective': 'Port the expert weight cache onto stock llama.cpp 9048bad for Muse Spark on DGX Spark.',
        'subject': {
            'engine': {'name': 'llama.cpp', 'revision': '9048bad8d6e3a0f9f1726e238e451181c7e02613'},
            'model': {'name': 'Muse-Spark-Open-Q2_K', 'format': 'gguf'},
        },
        'target': {'profile': 'spark-gb10', 'machine': 'DGX Spark GB10', 'arch': 'arm64', 'cuda': '13', 'sm': '121', 'node_count': 1},
        'acceptance_criteria': [
            {'id': 'gate_unset_parity', 'kind': 'correctness', 'verifiable_by': 'engine.build_expert_weight_cache.verify',
             'description': 'Greedy output matches stock byte-for-byte when gate is unset.'},
            {'id': 'client_ttft_ms', 'kind': 'metric', 'description': 'Client TTFT in ms (lower is better).'},
            {'id': 'single_spark_cap', 'kind': 'constraint', 'description': 'Run on one DGX Spark GB10 under 96 GiB.'},
        ],
        'constraints': {
            'allowed_effects': ['workspace.read', 'workspace.write', 'process.exec'],
            'budget': {'max_turns': 120, 'wall_clock_s': 7200},
        },
    }


def multi_ir(selection, capsules, option='M1', preflight=False, extra_steps=None):
    risky = {r['capsule'] for r in selection['risks']}
    by_cap = {c['capsule']: c for c in selection['candidates']}
    steps = [
        {'id': 'inspect_engine', 'kind': 'inspect', 'objective': 'Inspect pinned engine checkout.',
         'depends_on': [], 'capsules': ['factory.engine_inspector', 'factory.source_workbench']},
    ]
    preflight_list = []
    pf_step = {}
    diff_steps = []
    converter_step = None
    tool_steps = []
    for c in capsules:
        info = by_cap[c]
        unit = info['unit']
        if c in risky:
            preflight_list.append({'unit': unit, 'add': preflight, 'why': 'hardware risk check'})
            if preflight:
                pid = f'preflight_{unit}'
                steps.append({'id': pid, 'kind': 'inspect', 'objective': f'Check hardware applicability for {c}.',
                              'depends_on': ['inspect_engine'], 'capsules': [c, 'factory.engine_inspector']})
                pf_step[unit] = pid
    for c in capsules:
        info = by_cap[c]
        unit = info['unit']
        if info['kind'] == 'builder':
            sid = f'integrate_{unit}'
            steps.append({'id': sid, 'kind': 'integrate', 'objective': f'Integrate {c} behind its gate.',
                          'depends_on': [pf_step[unit]] if unit in pf_step else ['inspect_engine'],
                          'capsules': [c, 'factory.integration_skill', 'factory.source_workbench']})
            diff_steps.append(sid)
            if info.get('change_kind') == 'converter':
                converter_step = sid
    for c in capsules:
        info = by_cap[c]
        unit = info['unit']
        if info['kind'] != 'builder':
            sid = f'build_{unit}'
            deps = ['inspect_engine'] + ([converter_step] if converter_step else [])
            steps.append({'id': sid, 'kind': 'build', 'objective': f'Compile weight pack using {c}.',
                          'depends_on': deps, 'capsules': [c, 'engine.precision_lab']})
            tool_steps.append(sid)

    upstream = list(diff_steps)
    if len(diff_steps) >= 2:
        steps.append({'id': 'combine', 'kind': 'merge', 'objective': f'Merge concurrent diffs using {option}.',
                      'depends_on': list(diff_steps),
                      'capsules': ['factory.integration_skill', 'factory.source_workbench']})
        upstream = ['combine']

    steps.append({'id': 'build_candidate', 'kind': 'build', 'objective': 'Build final engine bundle.',
                  'depends_on': upstream + tool_steps, 'capsules': ['factory.builder', 'factory.lab_manager']})
    deliver_deps = ['build_candidate']
    if extra_steps:
        steps.extend(extra_steps)
        deliver_deps = ['build_candidate'] + [s['id'] for s in extra_steps]
    steps.append({'id': 'deliver_to_lab', 'kind': 'deliver', 'objective': 'Deliver verified artifacts to lab.',
                  'depends_on': deliver_deps, 'capsules': ['factory.lab_manager']})

    ir = {
        'format': 'factory.plan-ir/1',
        'selected_capsules': [{'capsule': c, 'why': 'selected'} for c in capsules],
        'preflight': preflight_list,
        'steps': steps,
    }
    if len(diff_steps) >= 2:
        ir['merge'] = {'option': option, 'why': 'test merge'}
    return ir


def test_shipped_task_inputs_and_catalog():
    shipped = req.shipped()
    assert {'star-deepseek-v2', 'muse-q2-ttft-v2'} <= set(shipped)
    assert req.problems(standalone_task_input()) == []
    catalog = plan_catalog.load()
    builders = sorted(c['id'] for c in catalog['capsules'].values() if c['builder'])
    assert builders == ['engine.build_batch_layout_mapper', 'engine.build_expert_weight_cache',
                        'observability.build_runtime_event_recorder', 'placement.build_weight_placement_planner',
                        'routing.build_expert_demand_predictor',
                        'weights.build_expert_scale_wiring', 'weights.build_muse_nvfp4_reader']
    assert catalog['capsules']['weights.build_weight_pack_compiler']['realizable']
    view = json.loads(plan_catalog.prompt_view(catalog))
    wpc = next(o for o in view['other_capsules'] if o['id'] == 'weights.build_weight_pack_compiler')
    assert 'weights.build_weight_pack_compiler.verify_pack' in wpc['verifiers']


@pytest.mark.parametrize('change, message', [
    (lambda r: r.pop('objective'), "'objective' is a required property"),
    (lambda r: r.pop('subject'), "'subject' is a required property"),
    (lambda r: r.pop('target'), "'target' is a required property"),
    (lambda r: r.pop('acceptance_criteria'), "'acceptance_criteria' is a required property"),
    (lambda r: r['constraints'].update(allowed_effects=['network.open']), 'unknown effects'),
    (lambda r: r.update(hints={'must_include': ['factory.builder']}), 'not a realizable capsule'),
    (lambda r: r.update(hints={'must_include': ['engine.build_expert_weight_cache'], 'excludes': ['engine.build_expert_weight_cache']}),
     'cannot be in both'),
    (lambda r: r['acceptance_criteria'].append(dict(r['acceptance_criteria'][0])), 'duplicate id'),
    (lambda r: r.update(task_template='no_such_task'), 'no task file'),
])
def test_task_input_problems(change, message):
    document = standalone_task_input()
    change(document)
    assert any(message in p for p in req.problems(document))


def test_single_capsule_compiles_without_merge_and_seeds(store, tmp_path):
    task_input = standalone_task_input()
    selection = plan_select.context(task_input)
    ir = multi_ir(selection, ['engine.build_expert_weight_cache'], preflight=False)
    document, plan, derivation = plan_compile.compile_plan(ir, selection, task_input)
    assert plan_checks.run(document, plan, task_input, plan_catalog.load()) == ([], [])

    nodes = nodes_of(document)
    assert set(nodes) == {'inspect_engine', 'integrate_cache', 'build_candidate', 'deliver_to_lab'}
    assert 'combine' not in nodes
    assert nodes['build_candidate']['predecessors'] == ['integrate_cache']
    assert 'gate_unset_parity' in nodes['integrate_cache']['requirement_ids']
    assert any('Greedy output matches stock' in c for c in nodes['integrate_cache']['outputs'][0]['criteria'])
    assert any('Run on one DGX Spark GB10' in c for c in nodes['build_candidate']['outputs'][0]['criteria'])
    assert any(d['rule'] == 'selected_capsule' for d in derivation)

    # Emits verified standard JSON deliverables (TLC ran internally) & seeds cleanly through init gate.
    directory = tmp_path / ai_planner.new_plan_id()
    directory.mkdir()
    run = ai_planner.PlanningRun(directory)
    verification = dict(execution_model=tla_check.execution_model(document), spec_sha256='0' * 64,
                        runs=[dict(run='safety', checked=['NoStuck'], distinct_states=1)])
    status = ai_planner._accept(run, task_input, ir, dict(node_contracts=document, plan=plan, derivation=derivation),
                               [], {}, verification)
    assert status['state'] == 'succeeded' and status['nodes'] == 4
    assert not (directory / 'graph.tla').exists()
    for present in ('contract.json', 'plan.json', 'graph.json', 'verification.json', 'task.json'):
        assert (directory / present).is_file(), present
    task = store.create_task(dict(task_id='single', objective='o', contract_id=str(directory / 'contract.json')))
    seeded = seed_plan(store, task, json.loads((directory / 'plan.json').read_text(encoding='utf-8')))
    assert len(seeded['nodes']) == 4 and seeded['history'][0]['planner'] == ai_planner.PLANNER


def test_selection_offers_candidates_risks_and_interference():
    star = req.load(STAR_INPUT)
    sel_star = plan_select.context(star)
    offered = {c['capsule'] for c in sel_star['candidates']}
    assert {'engine.build_expert_weight_cache', 'observability.build_runtime_event_recorder',
            'placement.build_weight_placement_planner', 'routing.build_expert_demand_predictor',
            'engine.build_batch_layout_mapper'} <= offered
    heavy = {frozenset((p['a'], p['b'])): p['weight'] for p in sel_star['interference']}
    assert heavy[frozenset(('cache', 'predictor'))] == 8 and heavy[frozenset(('cache', 'recorder'))] == 6
    assert sel_star['merge_options']['M2']['stages'][0]['members'] == ['cache', 'predictor', 'recorder']

    muse = req.load(MUSE_INPUT)
    sel_muse = plan_select.context(muse)
    by_cap = {c['capsule']: c for c in sel_muse['candidates']}
    assert by_cap['weights.build_muse_nvfp4_reader']['features']['hardware']['match'] is True
    assert by_cap['weights.build_expert_scale_wiring']['features']['hardware']['match'] is True
    assert by_cap['engine.build_expert_weight_cache']['features']['hardware']['match'] is False
    assert by_cap['weights.build_weight_pack_compiler']['kind'] == 'tool'


@pytest.mark.parametrize('change, message', [
    (lambda ir: ir['selected_capsules'][0].update(capsule='factory.builder'), 'not among offered candidates'),
    (lambda ir: ir['selected_capsules'].append(dict(ir['selected_capsules'][0])), 'listed twice'),
    (lambda ir: ir.update(selected_capsules=[]), 'at least one'),
    (lambda ir: ir['preflight'].pop(), 'decide whether to add a preflight step'),
    (lambda ir: ir['merge'].update(option='M9'), 'is not offered'),
    (lambda ir: ir.update(units=[{'id': 'pair', 'capsules': ['observability.build_runtime_event_recorder',
                                                              'engine.build_batch_layout_mapper']},
                                 {'id': 'cache', 'capsules': ['engine.build_expert_weight_cache']}]), 'share no ontology slice'),
    (lambda ir: ir.update(priority=[['cache', 'nowhere']]), 'must be [unit, unit]'),
])
def test_decisions_outside_the_options_are_refused(change, message):
    star = req.load(STAR_INPUT)
    sel = plan_select.context(star)
    ir = multi_ir(sel, ['observability.build_runtime_event_recorder',
                        'engine.build_expert_weight_cache',
                        'engine.build_batch_layout_mapper'])
    change(ir)
    assert any(message in p for p in plan_ir.problems(ir, sel))


def test_single_unit_forbids_merge_and_tool_cannot_share_unit():
    muse = req.load(MUSE_INPUT)
    sel = plan_select.context(muse)
    ir = multi_ir(sel, ['engine.build_expert_weight_cache'])
    ir['merge'] = {'option': 'M1', 'why': 'invalid'}
    assert any('fewer than two code-diff units' in p for p in plan_ir.problems(ir, sel))

    ir2 = {
        'format': 'factory.plan-ir/1',
        'selected_capsules': [
            {'capsule': 'weights.build_weight_pack_compiler', 'why': 'pack'},
            {'capsule': 'weights.build_expert_scale_wiring', 'why': 'wiring'},
        ],
        'units': [{'id': 'mixed', 'capsules': ['weights.build_weight_pack_compiler', 'weights.build_expert_scale_wiring']}],
        'steps': [
            {'id': 'inspect_engine', 'kind': 'inspect', 'objective': 'Inspect checkout.',
             'depends_on': [], 'capsules': ['factory.engine_inspector']},
            {'id': 'integrate_mixed', 'kind': 'integrate', 'objective': 'Mixed unit.',
             'depends_on': ['inspect_engine'],
             'capsules': ['weights.build_weight_pack_compiler', 'weights.build_expert_scale_wiring']},
            {'id': 'build_candidate', 'kind': 'build', 'objective': 'Build bundle.',
             'depends_on': ['integrate_mixed'], 'capsules': ['factory.builder']},
            {'id': 'deliver_to_lab', 'kind': 'deliver', 'objective': 'Deliver bundle.',
             'depends_on': ['build_candidate'], 'capsules': ['factory.lab_manager']},
        ],
    }
    assert any('tool capsules cannot share a unit' in p for p in plan_ir.problems(ir2, sel))


def test_static_checks_catch_planning_mistakes():
    task_input = standalone_task_input()
    task_input['hints'] = {'must_include': ['engine.build_expert_weight_cache'], 'excludes': ['engine.build_batch_layout_mapper']}
    sel = plan_select.context(task_input)
    ir = multi_ir(sel, ['engine.build_expert_weight_cache'])
    doc, plan, _ = plan_compile.compile_plan(ir, sel, task_input)
    cat = plan_catalog.load()
    assert plan_checks.run(doc, plan, task_input, cat) == ([], [])

    bad = copy.deepcopy(doc)
    nodes_of(bad)['deliver_to_lab']['requirement_ids'].remove('client_ttft_ms')
    assert any('criterion client_ttft_ms' in p for p in plan_checks.run(bad, plan, task_input, cat)[0])

    bad = copy.deepcopy(doc)
    nodes_of(bad)['integrate_cache']['verifiers'][0]['verifier'] = 'engine.build_expert_weight_cache.approve'
    assert any('is not a verify capability' in p for p in plan_checks.run(bad, plan, task_input, cat)[0])

    bad = copy.deepcopy(doc)
    nodes_of(bad)['inspect_engine']['authority_ceiling']['effects'].append('gpu.use')
    assert any("exceed the task's allowed effects" in p for p in plan_checks.run(bad, plan, task_input, cat)[0])

    bad = copy.deepcopy(doc)
    nodes_of(bad)['integrate_cache']['authority_ceiling'] = {'effects': ['workspace.read', 'process.exec'], 'workspace': 'read'}
    assert any('needs workspace write' in p for p in plan_checks.run(bad, plan, task_input, cat)[0])

    bad = copy.deepcopy(doc)
    nodes_of(bad)['build_candidate']['inputs'].append({'name': 'bad_in', 'from': 'deliver_to_lab.lab_request'})
    nodes_of(bad)['build_candidate']['predecessors'].append('deliver_to_lab')
    # deliver_to_lab cycle/port check catches invalid wiring
    assert plan_checks.run(bad, plan, task_input, cat)[0]


def test_muse_mixed_builder_and_tool_ccs_compile():
    muse = req.load(MUSE_INPUT)
    sel = plan_select.context(muse)
    capsules = [
        'weights.build_muse_nvfp4_reader',
        'weights.build_expert_scale_wiring',
        'weights.build_weight_pack_compiler',
        'engine.build_expert_weight_cache',
    ]
    ir = multi_ir(sel, capsules, option='M1', preflight=True)
    doc, plan, _ = plan_compile.compile_plan(ir, sel, muse)
    assert plan_checks.run(doc, plan, muse, plan_catalog.load()) == ([], [])
    nodes = nodes_of(doc)
    assert 'preflight_cache' in nodes['integrate_cache']['predecessors']
    assert 'build_compiler' in nodes
    assert {v['verifier'] for v in nodes['build_compiler']['verifiers']} == {
        'weights.build_weight_pack_compiler.verify_recipe',
        'weights.build_weight_pack_compiler.verify_pack',
    }
    assert {v['verifier'] for v in nodes['integrate_reader']['verifiers']} == {
        'weights.build_muse_nvfp4_reader.verify',
        'weights.build_muse_nvfp4_reader.verify_pack',
    }
    assert 'combine' in nodes and nodes['build_candidate']['predecessors'] == ['combine', 'build_compiler']


def test_loosened_limits_are_refused():
    task_input = standalone_task_input()
    sel = plan_select.context(task_input)
    ir = multi_ir(sel, ['engine.build_expert_weight_cache'])
    ir['limits'] = {'build_candidate': {'build_attempts': 9}}
    with pytest.raises(plan_compile.CompileError, match='limits may only tighten'):
        plan_compile.compile_plan(ir, sel, task_input)


def test_parse_reply():
    for text, msg in [
        ('I would plan five integrations.', 'no JSON object'),
        ('{"format": "factory.plan-ir/1", ', 'no JSON object'),
        ('{"format": "factory.plan-ir/1", "selected_capsules": [}', 'not valid JSON'),
        ('{"node_contracts": {}}', '"format": "factory.plan-ir/1"'),
    ]:
        ir, problem = ai_planner.parse_reply(text)
        assert ir is None and msg in problem
    ir, problem = ai_planner.parse_reply('```json\n{"format": "factory.plan-ir/1", "selected_capsules": []}\n```')
    assert problem is None and ir['selected_capsules'] == []


def test_prompt_offers_options_not_answers():
    star = req.load(STAR_INPUT)
    sel = plan_select.context(star)
    prompt = ai_planner.build_prompt(star, sel)
    assert 'engine.build_expert_weight_cache' in prompt and '"M2"' in prompt and 'interference' in prompt
    assert '## Full CC Library (Capability Capsules)' in prompt
    assert 'analysis.quant_kernel_profile' in prompt and 'factory.source_workbench' in prompt
    assert 'custom_workflow' not in prompt and 'slot_bindings' not in prompt
    assert 'node_contracts' not in prompt


def test_autonomous_steps_custom_cc_binding_and_validation(tmp_path):
    """Planner autonomously inserts measure/investigate steps and binds arbitrary CC Library capsules."""
    task_input = standalone_task_input()
    sel = plan_select.context(task_input)
    extra = [
        {
            'id': 'profile_kernels',
            'kind': 'measure',
            'objective': 'Profile quantization kernel occupancy after candidate build.',
            'depends_on': ['build_candidate'],
            'capsules': ['analysis.quant_kernel_profile', 'factory.lab_manager'],
            'limits': {'turns': 12},
        },
    ]
    ir = multi_ir(sel, ['engine.build_expert_weight_cache'], preflight=True, extra_steps=extra)
    doc, plan, derivation = plan_compile.compile_plan(ir, sel, task_input)
    assert plan_checks.run(doc, plan, task_input, plan_catalog.load()) == ([], [])
    assert tla_check.check(doc, tmp_path / 'autonomous-custom')['passed']
    nodes = nodes_of(doc)
    assert 'profile_kernels' in nodes
    assert nodes['profile_kernels']['work']['helpful_ccs'][0] == 'analysis.quant_kernel_profile'
    assert nodes['profile_kernels']['verifiers'][0]['verifier'].startswith('analysis.quant_kernel_profile.')

    bad_cc = copy.deepcopy(ir)
    bad_cc['steps'][0]['capsules'].append('nonexistent.fake_capsule')
    assert any('unknown CC Library capsule' in p for p in plan_ir.problems(bad_cc, sel))

    bad_kind = copy.deepcopy(ir)
    bad_kind['steps'][0]['kind'] = 'invented_kind'
    assert any('steps/inspect_engine/kind' in p for p in plan_ir.problems(bad_kind, sel))


def test_synthesize_feedback_loop_tlc_and_replay(tmp_path):
    """Round 1 misses preflight -> rejected by IR; Round 2 fixes it -> proven by TLC and replayable."""
    task_input = standalone_task_input()
    sel = plan_select.context(task_input)
    bad_reply = json.dumps(multi_ir(sel, ['engine.build_expert_weight_cache'], preflight=False))
    # Force bad IR to drop required preflight decision
    bad_obj = json.loads(bad_reply)
    bad_obj['preflight'] = []
    bad_reply = json.dumps(bad_obj)
    good_reply = json.dumps(multi_ir(sel, ['engine.build_expert_weight_cache'], preflight=True))
    replies = iter([bad_reply, good_reply])

    async def fake_invoke(prompt, system):
        return {'text': next(replies), 'identity': 'fake-model'}

    run_dir = tmp_path / ai_planner.new_plan_id()
    status = asyncio.run(ai_planner.synthesize(task_input, run_dir, invoke=fake_invoke))
    assert status['state'] == 'succeeded' and status['round'] == 2 and status['nodes'] == 5
    verdicts = ai_planner.replay(run_dir)
    assert [v['passed'] for v in verdicts] == [False, True]
    assert all(v['same'] for v in verdicts) and verdicts[-1]['same_graph']


def test_synthesize_tlc_repairs_starved_autonomous_step(tmp_path):
    """Round 1 legally zeroes build_attempts on an autonomous plan -> TLC NoStuck rejects -> Round 2 succeeds."""
    task_input = standalone_task_input()
    sel = plan_select.context(task_input)
    bad_ir = multi_ir(sel, ['engine.build_expert_weight_cache'], preflight=True)
    bad_ir['limits'] = {'build_candidate': {'build_attempts': 0}}
    good_ir = multi_ir(sel, ['engine.build_expert_weight_cache'], preflight=True)
    replies = iter([json.dumps(bad_ir), json.dumps(good_ir)])

    async def fake_invoke(prompt, system):
        return {'text': next(replies), 'identity': 'fake-model'}

    run_dir = tmp_path / ai_planner.new_plan_id()
    status = asyncio.run(ai_planner.synthesize(task_input, run_dir, invoke=fake_invoke))
    assert status['state'] == 'succeeded' and status['round'] == 2
    r1 = json.loads((run_dir / 'rounds' / '1' / 'result.json').read_text(encoding='utf-8'))
    assert r1['layer'] == 'tla' and any('get stuck' in p for p in r1['problems'])


def test_unrealizable_ir_rejects_cleanly(tmp_path):
    task_input = standalone_task_input()

    async def invoke_unr(prompt, system):
        return {'text': json.dumps({'format': 'factory.plan-ir/1', 'unrealizable': {'why': 'no matching capsule'}})}

    status = asyncio.run(ai_planner.synthesize(task_input, tmp_path / ai_planner.new_plan_id(), invoke=invoke_unr))
    assert status['state'] == 'rejected' and 'unrealizable_requirement' in status['error']


def test_planner_http_boundaries(tmp_path, monkeypatch):
    from jiuwenswarm.gateway.channel_manager.web.factory_planner_http import FactoryPlannerService, attach_planner_routes
    app = FastAPI()
    attach_planner_routes(app, service=FactoryPlannerService(tmp_path / 'runs'))
    api = TestClient(app)
    listing = api.get('/api/factory/planner/requirements').json()
    assert [r['id'] for r in listing['requirements']] == ['muse-q2-ttft-v2', 'star-deepseek-v2']
    assert all(r['problems'] == [] for r in listing['requirements'])
    assert 'tlc' in listing['environment']
    assert api.get('/api/factory/planner/codex/status').status_code == 200
    assert api.post('/api/factory/planner/codex/login', headers={'origin': 'http://evil.example'}).status_code == 403
    assert api.post('/api/factory/planner/codex/cancel', json={'login_attempt_id': 'x'}, headers={'origin': 'http://evil.example'}).status_code == 403
    assert api.post('/api/factory/planner/codex/logout', headers={'origin': 'http://evil.example'}).status_code == 403

    from jiuwenswarm.gateway.channel_manager.web.factory_planner_http import _sanitize_codex_payload
    sample_auth = 'https://auth.openai.com/oauth/authorize?response_type=code&code_challenge=VbBVxCQrDEOg9YUrYgIu05qT1WVOqjAuQOuA376nRf8&state=cWvbBmIxcNYVDEB2X-g937x9sp8dVvA6TDdxMFDAWiU'
    cleaned_codex = _sanitize_codex_payload({'state': 'signing_in', 'auth_url': sample_auth, 'error': 'Bearer sk-12345678901234567890abcd'})
    assert cleaned_codex['auth_url'] == sample_auth and '<redacted>' not in cleaned_codex['auth_url']
    assert '<redacted>' in cleaned_codex['error']
    untrusted_codex = _sanitize_codex_payload({'auth_url': 'https://evil.example/oauth?state=abcdefghijklmno&code_challenge=abcdefghijklmno'})
    assert '<redacted>' in untrusted_codex['auth_url']

    assert api.get('/api/factory/planner/runs').json() == {'runs': [], 'busy': []}
    assert api.get('/api/factory/planner/runs/../../etc').status_code == 404
    assert api.get('/api/factory/planner/runs/plan-20261124T000000Z-abcdef').status_code == 404
    assert api.post('/api/factory/planner/runs', json={'requirements_id': 'nope'}).status_code == 404
    bad = standalone_task_input()
    bad.pop('subject')
    response = api.post('/api/factory/planner/runs', json={'requirements': bad})
    assert response.status_code == 422
    assert api.post('/api/factory/planner/runs', json={'requirements_id': 'star-deepseek-v2'},
                    headers={'origin': 'http://evil.example'}).status_code == 403
    # Loopback dev-proxy origin (e.g. Vite 127.0.0.1:5173 -> backend 127.0.0.1:19000) is allowed cleanly
    loopback_req = api.post(
        '/api/factory/planner/runs',
        json={'requirements': bad},
        headers={'origin': 'http://127.0.0.1:5173', 'host': '127.0.0.1:19000'},
    )
    assert loopback_req.status_code == 422

    # Workflow Library endpoints are decommissioned (autonomous planning directly against CC Library)
    assert api.get('/api/factory/planner/workflows').status_code == 404
    assert api.post('/api/factory/planner/workflows/distill', json={'text': 'all:\n\techo ok'}).status_code == 404

    # Ablation telemetry & origin/TLC checks
    ablation = api.get('/api/factory/planner/ablation')
    assert ablation.status_code == 200
    ab_json = ablation.json()
    assert ab_json['available'] is True
    assert ab_json['results']['summary']['class_b_count'] == 10
    assert api.post('/api/factory/planner/ablation/run', headers={'origin': 'http://evil.example'}).status_code == 403

    monkeypatch.setenv('FACTORY_TLA2TOOLS', str(tmp_path / 'missing.jar'))
    response = api.post('/api/factory/planner/runs', json={'requirements_id': 'star-deepseek-v2'})
    assert response.status_code == 503 and 'TLC is unavailable' in response.json()['detail']
    response_ab = api.post('/api/factory/planner/ablation/run')
    assert response_ab.status_code == 503 and 'TLC is unavailable' in response_ab.json()['detail']


def test_planner_http_detail_returns_verified_json_outputs(tmp_path):
    from jiuwenswarm.gateway.channel_manager.web.factory_planner_http import FactoryPlannerService, attach_planner_routes
    task_input = standalone_task_input()
    sel = plan_select.context(task_input)
    good_ir = multi_ir(sel, ['engine.build_expert_weight_cache'], preflight=True)
    plan_dir = tmp_path / 'plan-20261125T000001Z-a1b2c3'

    async def invoke_ok(prompt, system):
        return {'text': json.dumps(good_ir)}

    status = asyncio.run(ai_planner.synthesize(task_input, plan_dir, invoke=invoke_ok))
    assert status['state'] == 'succeeded'
    assert not (plan_dir / 'graph.tla').exists()

    app = FastAPI()
    attach_planner_routes(app, service=FactoryPlannerService(tmp_path, ablation_dir=tmp_path / 'missing_ablation'))
    api = TestClient(app)
    res = api.get(f'/api/factory/planner/runs/{plan_dir.name}')
    assert res.status_code == 200
    body = res.json()
    assert {'contract.json', 'plan.json', 'graph.json', 'verification.json'} <= set(body['outputs'])
    assert 'graph.tla' not in body['outputs']
    assert body['graph_tla_info'] is None
    assert body['graph']['nodes'] and body['node_contracts']['nodes'] and body['verification']['passed'] is True
    dl = api.get(f'/api/factory/planner/runs/{plan_dir.name}/graph.json')
    assert dl.status_code == 200
    assert dl.headers.get('content-disposition') == 'attachment; filename="graph.json"'
    dl_json = dl.json()
    assert dl_json['verification']['static_checks']['passed'] is True
    assert dl_json['verification']['tlc']['passed'] is True
    assert dl_json['execution_model']['proven']

    # Failed / unverified runs cannot download graph.json
    unverified_dir = tmp_path / 'plan-20261125T000002Z-b2c3d4'
    unverified_dir.mkdir()
    (unverified_dir / 'status.json').write_text(json.dumps({'state': 'failed'}), encoding='utf-8')
    assert api.get(f'/api/factory/planner/runs/{unverified_dir.name}/graph.json').status_code == 404

    empty_ab = api.get('/api/factory/planner/ablation').json()
    assert empty_ab['available'] is False and empty_ab['results'] is None


def test_without_tlc_the_planner_refuses_before_calling_the_model(tmp_path, monkeypatch):
    monkeypatch.setenv('FACTORY_TLA2TOOLS', str(tmp_path / 'missing.jar'))
    calls = []

    async def must_not_be_called(prompt, system):
        calls.append(prompt)
        raise AssertionError('the model was called although nothing could be proven')
    status = asyncio.run(ai_planner.synthesize(standalone_task_input(), tmp_path / 'run', invoke=must_not_be_called))
    assert status['state'] == 'failed' and 'TLC unavailable' in status['error'] and calls == []


@pytest.mark.skipif(os.environ.get('FACTORY_PLANNER_LIVE') != '1',
                    reason='live: set FACTORY_PLANNER_LIVE=1 with a signed-in Codex subscription and TLC installed')
def test_live_codex_plans_star_deepseek_v2(tmp_path):
    from jiuwenswarm.server.runtime.codex_subscription.service import get_service

    async def go():
        try:
            return await ai_planner.synthesize(req.load(STAR_INPUT), tmp_path / 'run')
        finally:
            await get_service().transport.close()
    status = asyncio.run(go())
    assert status['state'] == 'succeeded', status
    verdicts = ai_planner.replay(tmp_path / 'run')
    assert all(v['same'] for v in verdicts) and verdicts[-1]['same_graph']
