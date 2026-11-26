"""Tests for bridging M1 ``binding.plan_checks`` alongside M2 rules and TLC."""
from __future__ import annotations

import copy
from pathlib import Path

from jiuwenswarm.factory import (
    m1_verifier_bridge,
    plan_catalog,
    plan_checks,
    plan_compile,
    plan_select,
    requirements as req,
    tla_check,
    tla_graph,
)

SHIPPED = Path(__file__).resolve().parents[2] / 'jiuwenswarm' / 'factory' / 'requirements'


def _star_single():
    star = req.load(SHIPPED / 'star-deepseek-v2.json')
    cat = plan_catalog.load()
    sel = plan_select.context(star, cat)
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
    return star, cat, sel, doc, plan


def test_m1_bridge_executes_real_binding_and_passes_healthy_plans():
    star, cat, _, doc, plan = _star_single()
    res = m1_verifier_bridge.run_m1_plan_checks(doc, plan, star, cat)
    assert res['executed'] is True
    assert res['passed'] is True
    assert res['problems'] == []
    assert res['summary']['passed'] >= 10 and res['summary']['failed'] == 0
    assert len(m1_verifier_bridge.M1_LIMITATIONS) == 4
    assert plan_checks.run(doc, plan, star, cat) == ([], [])


def test_m1_bridge_retains_legacy_m1_checks():
    star, cat, _, doc, plan = _star_single()

    # 1. Predecessor cycle -> caught by M1 acyclicity (kahn_order)
    cyc = copy.deepcopy(doc)
    cyc['nodes'][0]['predecessors'] = ['integrate_cache']
    m1_cyc = m1_verifier_bridge.run_m1_plan_checks(cyc, plan, star, cat)
    assert not m1_cyc['passed']
    assert any('acyclicity' in p for p in m1_cyc['problems'])

    # 2. Missing requirement tag -> caught by M1 brief_coverage
    cov = copy.deepcopy(doc)
    cov['nodes'][-1]['requirement_ids'] = []
    m1_cov = m1_verifier_bridge.run_m1_plan_checks(cov, plan, star, cat)
    assert not m1_cov['passed']
    assert any('brief_coverage' in p for p in m1_cov['problems'])

    # 3. Unknown effect outside task allowed_effects -> caught by M1 effects_within_policy AND M2 authority
    eff = copy.deepcopy(doc)
    eff['nodes'][0]['authority_ceiling']['effects'].append('gpu.use')
    m1_eff = m1_verifier_bridge.run_m1_plan_checks(eff, plan, star, cat)
    assert not m1_eff['passed']
    assert any('effects_within_policy' in p for p in m1_eff['problems'])
    assert any('effects_within_policy' in p for p in plan_checks.run(eff, plan, star, cat)[0])


def test_four_m1_gaps_bypass_raw_m1_and_require_tlc(tmp_path):
    star, cat, sel, doc, plan = _star_single()

    # Gap 1: build_attempts == 0 passes raw M1 binding.plan_checks, blocked by TLC NoStuck
    starved = copy.deepcopy(doc)
    for n in starved['nodes']:
        if n['node_id'] == 'build_candidate':
            n['node_limits'] = {'turns': 15, 'build_attempts': 0}
    assert m1_verifier_bridge.run_m1_plan_checks(starved, plan, star, cat)['passed'] is True
    assert not tla_check.check_graph_tla(tla_graph.render_graph_tla(starved, star, plan), tmp_path / 'gap1')['passed']

    # Gap 2: scheduler plan.depends_on cycle while node.predecessors is acyclic -> passes M1 kahn_order, blocked by TLC
    ir_multi = {
        'format': 'factory.plan-ir/1',
        'selected_capsules': [
            {'capsule': 'observability.build_runtime_event_recorder', 'why': 'rec'},
            {'capsule': 'engine.build_expert_weight_cache', 'why': 'cache'},
        ],
        'preflight': [
            {'unit': 'cache', 'add': False, 'why': 'no'},
            {'unit': 'recorder', 'add': False, 'why': 'no'},
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
    mdoc, mplan, _ = plan_compile.compile_plan(ir_multi, sel, star)
    cyclic_plan = copy.deepcopy(mplan)
    for pn in cyclic_plan['nodes']:
        if pn['node_id'] == 'integrate_cache':
            pn['depends_on'].append('integrate_recorder')
        elif pn['node_id'] == 'integrate_recorder':
            pn['depends_on'].append('integrate_cache')
    assert m1_verifier_bridge.run_m1_plan_checks(mdoc, cyclic_plan, star, cat)['passed'] is True
    assert not tla_check.check_graph_tla(tla_graph.render_graph_tla(mdoc, star, cyclic_plan), tmp_path / 'gap3')['passed']

    # Gap 3: omitted concurrent checkout lock -> passes raw M1, blocked by TLC ExclusiveResources
    assert m1_verifier_bridge.run_m1_plan_checks(mdoc, mplan, star, cat)['passed'] is True
    race_tla = tla_graph.render_graph_tla(mdoc, star, mplan, exclusive_override={'integrate_cache': [], 'integrate_recorder': []})
    assert not tla_check.check_graph_tla(race_tla, tmp_path / 'gap2')['passed']

    # Gap 4: deliver granted workspace=write (allowed at task level) -> passes raw M1 coarse effect_class, caught by ASSUME
    overpriv = copy.deepcopy(doc)
    overpriv['nodes'][-1]['authority_ceiling'] = {'effects': ['process.exec', 'workspace.read', 'workspace.write'], 'workspace': 'write'}
    assert m1_verifier_bridge.run_m1_plan_checks(overpriv, plan, star, cat)['passed'] is True
    assert not tla_check.check_graph_tla(tla_graph.render_graph_tla(overpriv, star, plan), tmp_path / 'gap4')['passed']
