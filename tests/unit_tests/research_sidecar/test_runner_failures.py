"""No run acknowledgement is invented for a known HTTP refusal."""
import asyncio
import json

from jiuwenswarm.research_sidecar.client import ClientError
from jiuwenswarm.research_sidecar.ledger import Ledger
from jiuwenswarm.research_sidecar.runner import Runner


def test_known_refusal_retains_source_error_and_does_not_count_an_unlaunched_run(tmp_path):
    error={'schema_version':'1.0.0','id':'error:controlled','category':'validation','message':'Controlled refusal.',
        'request_id':'request','run_id':None,'evidence_refs':[],'correction':'Inspect the controlled request.'}
    class RefusingDouble:
        async def readiness(self):return {'build_id':'controlled','client_contract_version':'1.0.0','pins':{
            'library_snapshot_sha256':'a'*64,'router_enabled':False},'ready':True,'operations':['submit']}
        async def submit(self,_):raise ClientError('product HTTP refused operation: 422',status_code=422,response_record=error)
    row={'run_id':'row','campaign_id':'campaign','case_id':'case','case_version':1,'config_id':'controlled','repeat_index':0}
    ledger=Ledger(tmp_path/'ledger.sqlite');runner=Runner(RefusingDouble(),ledger,tmp_path)
    result=asyncio.run(runner.execute(row,{'entry_mode':'run'},inventory={'readiness':'ready','inventory_id':'inventory'},
        submission={'client_request_id':'request'},expected_pins={}))
    assert result['outcome']=='blocked' and result['launched'] is False and result['app_run_id'] is None
    assert result['outcome_detail']['product_decision']=='validation'
    assert json.loads((tmp_path/'runs/row/client-error.json').read_bytes())==error
    assert any(event['kind']=='refused' for event in ledger.events('row'))
    assert not result['model_calls'] and result['cost']['monetary'] is None
    ledger.close()
