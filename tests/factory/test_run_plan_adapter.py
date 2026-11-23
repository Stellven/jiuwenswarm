import json
from pathlib import Path

from jiuwenswarm.factory.run_plan_adapter import from_run_plan, validate


EXAMPLE = (Path(__file__).resolve().parents[2] / 'docs' / 'architecture' /
           'design-package' / 'reference' / 'examples' / 'run_plan.json')


def test_from_run_plan():
    run_plan = json.loads(EXAMPLE.read_text(encoding='utf-8'))
    document = from_run_plan(run_plan)

    assert validate(document) == []
    assert [node['node_id'] for node in document['nodes']] == [
        node['node_id'] for node in run_plan['nodes']]
    for source, node in zip(run_plan['nodes'], document['nodes']):
        assert node['predecessors'] == source['predecessors']
        assert node['requirement_ids'] == source['requirement_ids'] + source['deliverable_ids']
        assert node['node_limits']['time_s'] == source['limits']['time_s']
        assert node['work']['helpful_ccs'] == [source['cc']['cc_name']]
        assert node['verifiers'] == [
            {'output': output['name'], 'review': True} for output in node['outputs']]
        successors = [other['node_id'] for other in run_plan['nodes']
                      if source['node_id'] in other['predecessors']]
        if successors:
            assert node['kind'] == 'investigate'
            assert node['hands_to'] == min(successors, key=run_plan['topological_order'].index)
        else:
            assert node['node_id'] == 'delivery'
            assert node['kind'] == 'deliver'
            assert node['hands_to'] == 'lab_manager'
        for original, port in zip(source['inputs'], node['inputs']):
            if original['future']:
                future = original['future']
                assert port['from'] == f"{future['producer_node']}.{future['port']}"
            else:
                assert port['from'] == 'task:source'
        assert all(len(output['criteria']) == 1 for output in node['outputs'])

    # The factory runs a plan only when its last node hands an engine to the lab manager;
    # a research plan ends in a report, and that is the one thing the factory asks for.
    from jiuwenswarm.factory.node_contract import problems
    assert problems(document) == ['delivery/outputs: the deliver node produces a required lab_request']
    assert all(v['review'] for node in document['nodes'] for v in node['verifiers'])  # reviews read evidence too


def test_missing_predecessor():
    run_plan = json.loads(EXAMPLE.read_text(encoding='utf-8'))
    run_plan['nodes'][0]['predecessors'] = ['missing_node']

    problems = validate(from_run_plan(run_plan))

    assert any('predecessor missing_node does not exist' in problem for problem in problems)
