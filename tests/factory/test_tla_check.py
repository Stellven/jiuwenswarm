"""TLC proves task graphs against the factory execution model (tla/TaskGraphExec.tla).

Runs the real TLC on reviewed reference graphs, deliberate breakages, and single-solution
TaskInput-compiled graphs (1-capsule, multi-capsule M1/M2/M3, and Muse mixed CCs).
Needs Java 11+ and tla2tools.jar (FACTORY_TLA2TOOLS or third_party/tlaplus).
"""
import copy

import pytest

from jiuwenswarm.factory import contract, plan_compile, plan_select, requirements as req, tla_check
from jiuwenswarm.factory.requirements import SHIPPED

try:
    tla_check.tools()
    MISSING = None
except tla_check.TlaUnavailable as exc:
    MISSING = str(exc)

pytestmark = pytest.mark.skipif(MISSING is not None, reason=f'TLC unavailable: {MISSING}')


@pytest.fixture
def star():
    c = contract.load('star-deepseek-v2')
    return copy.deepcopy(c['extensions']['factory.node-contracts'])


def node(document, key):
    return next(n for n in document['nodes'] if n['node_id'] == key)


def test_the_reviewed_graph_is_proven(star, tmp_path):
    result = tla_check.check(star, tmp_path)
    assert result['passed'] and result['problems'] == []
    safety, delivery = result['runs']
    assert safety['run'] == 'safety' and 'Termination' in safety['checked'] and 'NoStuck' in safety['checked']
    assert delivery['run'] == 'delivery' and 'HaltsDelivered' in delivery['checked']
    assert safety['distinct_states'] > 1000 and delivery['distinct_states'] > 1000
    assert len(result['spec_sha256']) == 64 and len(result['tla2tools_sha256']) == 64


def test_a_serial_scheduler_is_also_safe(star, tmp_path):
    assert tla_check.check(star, tmp_path, max_parallel=1)['passed']


def test_a_build_step_without_attempts_gets_the_run_stuck(star, tmp_path):
    """Well-formed to every static rule, yet no execution can deliver."""
    node(star, 'build_candidate')['node_limits']['build_attempts'] = 0
    result = tla_check.check(star, tmp_path)
    assert not result['passed']
    problem = result['problems'][0]
    assert problem.startswith('TLC NoStuck: the run can get stuck')
    assert 'build_candidate cannot start: it has used 0 of 0 allowed attempts' in problem
    assert 'final: done [combine' in problem
    assert result['runs'][0]['violation']['property'] == 'NoStuck'


def test_trace_parsing_of_real_tlc_output():
    output = '''Error: Invariant NoStuck is violated.
Error: The behavior up to this point is:
State 1: <Initial predicate>
/\\ att = [a |-> 0, b |-> 0]
/\\ st = [a |-> "waiting", b |-> "waiting"]

State 2: <Start("a") line 61, col 13 to line 56, col 47 of module TaskGraphExec>
/\\ att = [a |-> 1, b |-> 0]
/\\ st = [a |-> "active", b |-> "waiting"]

State 3: <Succeed("a") line 66, col 20 to line 68, col 35 of module TaskGraphExec>
/\\ att = [a |-> 1, b |-> 0]
/\\ st = [a |-> "done", b |-> "waiting"]

9 states generated, 5 distinct states found, 0 states left on queue.
'''
    trace = tla_check.parse_trace(output)
    assert [s['state'] for s in trace] == [1, 2, 3]
    assert trace[-1]['st'] == {'a': 'done', 'b': 'waiting'} and trace[1]['att'] == {'a': 1, 'b': 0}
    model = dict(preds={'a': [], 'b': ['a']}, limits={'a': 2, 'b': 0}, exclusive={'a': [], 'b': []}, max_parallel=4)
    assert tla_check.blocked(trace[-1], model) == ['b cannot start: it has used 0 of 0 allowed attempts (its attempt limit is 0)']
    assert tla_check.describe(trace).startswith('a waiting→active (attempt 1); a active→done')


def test_termination_is_a_property_of_the_model(tmp_path):
    """Every step lowers Rank, whatever the graph: checked once here, not per plan."""
    model = dict(preds={'a': [], 'b': ['a'], 'c': ['a'], 'd': ['b', 'c']}, deliver='d', max_parallel=2,
                 limits={'a': 2, 'b': 2, 'c': 3, 'd': 1}, exclusive={'a': [], 'b': ['checkout'], 'c': ['checkout'], 'd': []})
    (tmp_path / 'TaskGraphExec.tla').write_text(tla_check.SPEC.read_text())
    (tmp_path / 'Plan.tla').write_text(tla_check.plan_module(model))
    for name, cooperative in (('rank', False), ('rank_coop', True)):
        (tmp_path / f'{name}.cfg').write_text(tla_check.config(model, cooperative, properties=('Termination',)))
        output, timed_out, _ = tla_check.run_tlc(tmp_path, name, timeout=120)
        assert not timed_out and 'Model checking completed. No error has been found.' in output, output[-2000:]


def test_compiled_single_and_multi_capsule_plans_are_proven(tmp_path):
    star_in = req.load(SHIPPED / 'star-deepseek-v2.json')
    sel = plan_select.context(star_in)
    risky = {r['capsule'] for r in sel['risks']}
    by_cap = {c['capsule']: c for c in sel['candidates']}

    # 1. Single capsule (no merge)
    ir_one = {
        'format': 'factory.plan-ir/1',
        'selected_capsules': [{'capsule': 'engine.build_expert_weight_cache', 'why': 'TTFT'}],
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
    doc_one, _, _ = plan_compile.compile_plan(ir_one, sel, star_in)
    assert tla_check.check(doc_one, tmp_path / 'single')['passed']

    # 2. Multi-capsule M1 and M2
    caps = ['observability.build_runtime_event_recorder', 'engine.build_expert_weight_cache',
            'routing.build_expert_demand_predictor', 'engine.build_batch_layout_mapper']
    multi_steps = [
        {'id': 'inspect_engine', 'kind': 'inspect', 'objective': 'Inspect checkout.',
         'depends_on': [], 'capsules': ['factory.engine_inspector']},
        *[
            {'id': f'integrate_{by_cap[c]["unit"]}', 'kind': 'integrate', 'objective': f'Integrate {c}.',
             'depends_on': ['inspect_engine'], 'capsules': [c]}
            for c in caps
        ],
        {'id': 'combine', 'kind': 'merge', 'objective': 'Merge concurrent diffs.',
         'depends_on': [f'integrate_{by_cap[c]["unit"]}' for c in caps], 'capsules': ['factory.integration_skill']},
        {'id': 'build_candidate', 'kind': 'build', 'objective': 'Build bundle.',
         'depends_on': ['combine'], 'capsules': ['factory.builder']},
        {'id': 'deliver_to_lab', 'kind': 'deliver', 'objective': 'Deliver to lab.',
         'depends_on': ['build_candidate'], 'capsules': ['factory.lab_manager']},
    ]
    for option in ('M1', 'M2'):
        ir = {
            'format': 'factory.plan-ir/1',
            'selected_capsules': [{'capsule': c, 'why': 'x'} for c in caps],
            'preflight': [{'unit': by_cap[c]['unit'], 'add': False, 'why': 'x'} for c in caps if c in risky],
            'merge': {'option': option, 'why': 'x'},
            'steps': multi_steps,
        }
        doc, _, _ = plan_compile.compile_plan(ir, sel, star_in)
        assert tla_check.check(doc, tmp_path / option)['passed'], option


def test_muse_reviewed_and_compiled_graphs_are_proven(tmp_path):
    c = contract.load('muse-q2-ttft-v2')
    reviewed = copy.deepcopy(c['extensions']['factory.node-contracts'])
    res_rev = tla_check.check(reviewed, tmp_path / 'muse-reviewed')
    assert res_rev['passed'] and res_rev['runs'][0]['distinct_states'] > 1000

    muse_in = req.load(SHIPPED / 'muse-q2-ttft-v2.json')
    sel = plan_select.context(muse_in)
    caps = ['weights.build_muse_nvfp4_reader', 'weights.build_expert_scale_wiring',
            'weights.build_weight_pack_compiler', 'engine.build_expert_weight_cache']
    ir = {
        'format': 'factory.plan-ir/1',
        'selected_capsules': [{'capsule': cap, 'why': 'x'} for cap in caps],
        'preflight': [{'unit': 'cache', 'add': True, 'why': 'sm_87 vs sm_121'}],
        'merge': {'option': 'M1', 'why': 'combine engine/converter diffs'},
        'steps': [
            {'id': 'inspect_engine', 'kind': 'inspect', 'objective': 'Inspect checkout.',
             'depends_on': [], 'capsules': ['factory.engine_inspector']},
            {'id': 'preflight_cache', 'kind': 'inspect', 'objective': 'Check cache applicability.',
             'depends_on': ['inspect_engine'], 'capsules': ['engine.build_expert_weight_cache']},
            {'id': 'integrate_reader', 'kind': 'integrate', 'objective': 'Integrate NVFP4 reader.',
             'depends_on': ['inspect_engine'], 'capsules': ['weights.build_muse_nvfp4_reader']},
            {'id': 'integrate_wiring', 'kind': 'integrate', 'objective': 'Integrate expert scale wiring.',
             'depends_on': ['inspect_engine'], 'capsules': ['weights.build_expert_scale_wiring']},
            {'id': 'integrate_cache', 'kind': 'integrate', 'objective': 'Integrate expert cache.',
             'depends_on': ['preflight_cache'], 'capsules': ['engine.build_expert_weight_cache']},
            {'id': 'build_compiler', 'kind': 'build', 'objective': 'Compile NVFP4 weight pack.',
             'depends_on': ['inspect_engine', 'integrate_reader'], 'capsules': ['weights.build_weight_pack_compiler']},
            {'id': 'combine', 'kind': 'merge', 'objective': 'Combine diffs.',
             'depends_on': ['integrate_reader', 'integrate_wiring', 'integrate_cache'],
             'capsules': ['factory.integration_skill']},
            {'id': 'build_candidate', 'kind': 'build', 'objective': 'Build candidate bundle.',
             'depends_on': ['combine', 'build_compiler'], 'capsules': ['factory.builder']},
            {'id': 'deliver_to_lab', 'kind': 'deliver', 'objective': 'Deliver to lab.',
             'depends_on': ['build_candidate'], 'capsules': ['factory.lab_manager']},
        ],
    }
    doc, _, _ = plan_compile.compile_plan(ir, sel, muse_in)
    res_cmp = tla_check.check(doc, tmp_path / 'muse-compiled')
    assert res_cmp['passed'] and res_cmp['runs'][0]['distinct_states'] > 1000
