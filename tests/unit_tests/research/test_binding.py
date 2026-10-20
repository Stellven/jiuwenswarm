import pytest

from jiuwenswarm.research.binding import expand_selectors, kahn_order
from jiuwenswarm.research.contracts import ResearchError


def test_kahn_order_uses_source_list_ties_and_rejects_cycles():
    nodes = [{'node_id':'second','predecessors':[]},{'node_id':'first','predecessors':[]},
             {'node_id':'last','predecessors':['first','second']}]
    assert kahn_order(nodes) == ['second','first','last']
    with pytest.raises(ResearchError, match='acyclicity'):
        kahn_order([{'node_id':'x','predecessors':['y']},{'node_id':'y','predecessors':['x']}])


def test_static_selectors_expand_against_each_actual_brief():
    template={'nodes':[{'requirement_ids':['all_mandatory_requirements'],'deliverable_ids':['all_deliverables']}],
              'coverage':[{'selector':'all_mandatory_requirements','node_ids':['node']} ]}
    brief={'mandatory_requirements':[{'id':'r1'}],'deliverables':[{'id':'d1'}],'evidence_obligations':[]}
    expanded=expand_selectors(template,brief)
    assert expanded['nodes'][0]['requirement_ids']==['r1']
    assert expanded['coverage']==[{'item_id':'r1','item_kind':'requirement','node_ids':['node']}]
    assert template['nodes'][0]['requirement_ids']==['all_mandatory_requirements']
