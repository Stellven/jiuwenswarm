import pytest

from jiuwenswarm.research.planning import parse_planner_reply, selected_plan_source
from jiuwenswarm.research.contracts import ResearchError


def test_plan_source_is_preselected_static_default_and_never_fallback():
    assert selected_plan_source({})=='static'
    assert selected_plan_source({'plan_source':'planned'})=='planned'
    with pytest.raises(ResearchError):selected_plan_source({'plan_source':'repair'})


def test_infeasible_is_bounded_single_line_without_graph():
    assert parse_planner_reply('INFEASIBLE: unavailable capability')==('infeasible','INFEASIBLE: unavailable capability')
    for raw in ['INFEASIBLE: x\n{}','INFEASIBLE: '+'x'*300,'INFEASIBLE:']:
        with pytest.raises(ResearchError):parse_planner_reply(raw)
