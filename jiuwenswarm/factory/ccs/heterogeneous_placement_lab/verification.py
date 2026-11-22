"""Standalone observable CPU checks; no runner certification."""
import json
from pathlib import Path
from components.placement import plan, execute_reference, overlap_schedule


def verify():
    root=Path(__file__).parent/'fixtures'
    load=lambda name: json.loads((root/(name+'.json')).read_text())
    request=load('plan'); result=plan(request)
    assert result['selected_experts']==list(range(6))
    assert all(x['device']=='gpu' for x in result['decisions'])
    request['physical_capacity_bytes']=6100
    assert all(x['device']=='cpu' for x in plan(request)['decisions'])
    request['physical_capacity_bytes']=6099
    try: plan(request)
    except ValueError: pass
    else: raise AssertionError('shared capacity overflow accepted')
    execution=execute_reference(load('execute_reference'))
    assert execution['output']==[27,36] and execution['executed_experts']==list(range(6))
    schedule=overlap_schedule(load('overlap_schedule'))
    assert schedule['serial_ms']==16 and schedule['optimistic_overlap_ms']==13
    assert schedule['events'][1]['compute_start_ms']==8
    return {'passed':True,'scope':'cpu_reference_only','checks':5}

if __name__=='__main__':print(json.dumps(verify()))
