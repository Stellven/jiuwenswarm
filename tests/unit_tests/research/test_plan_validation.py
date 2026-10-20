"""Original documentation fixtures exercise deterministic validation only."""
import copy
import json
from pathlib import Path

import pytest

from jiuwenswarm.research.binding import plan_checks


def fixtures():
    root=Path('tests/fixtures/research/planning')
    return [json.loads((root/name).read_text('utf-8')) for name in ('static_template.json','lifecycle_research_brief.json','library_snapshot.json','resource_inventory.json','plan_policy.json')]


@pytest.mark.parametrize('fault,expected',[
    (None,None),('structure','template_structure'),('cycle','acyclicity'),('coverage','brief_coverage'),
    ('membership','library_membership'),('pins','mandatory_check_bundle_present'),('input','port_type_compatibility'),
    ('future','dependency_closure'),('effect','effects_within_policy'),('resource','resource_feasibility'),
    ('budget','budget_ceilings'),('delivery','delivery_leaf_coverage'),('retry','budget_ceilings')])
def test_shared_static_checks_reject_actual_source_invariants(fault,expected):
    source,brief,library,resources,policy=fixtures();original=copy.deepcopy(source)
    if fault=='structure':source['unexpected_authority']='grant'
    if fault=='cycle':source['nodes'][0]['predecessors']=['delivery']
    if fault=='coverage':source['coverage']=[]
    if fault=='membership':source['nodes'][0]['cc']['declaration_sha256']='a'*64
    if fault=='input':source['nodes'][0]['inputs']=[]
    if fault=='future':next(p for p in source['nodes'][1]['inputs'] if p['source_kind']=='future_output')['future']['producer_node']='missing'
    if fault=='effect':policy['allowed_effect_classes']=['pure']
    if fault=='resource':
        for resource in resources['resources']:resource['available']=False
    if fault=='budget':source['limits']['model_calls']=0
    if fault=='delivery':source['nodes'][-1]['deliverable_ids']=[]
    if fault=='retry':policy['max_attempts_per_node']=2
    bound,results=plan_checks(source,brief,library,resources,policy,plan_source='static',pin_exists=lambda pins:fault!='pins')
    if fault is None:
        assert all(row['outcome']=='PASS' for row in results)
        assert source==original and bound!=source
    else:assert next(row for row in results if row['check_id']==expected)['outcome']=='FAIL'
