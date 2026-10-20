from copy import deepcopy
import json
from pathlib import Path
import pytest
from jiuwenswarm.research_router.request_validation import ProtectedData,validate_request,IntegrityFault
from jiuwenswarm.research_router.request_validation import CATEGORIES
from jiuwenswarm.research_router.contracts import ContractData


FIXTURE=Path(__file__).resolve().parents[2]/'fixtures'/'research'/'router'/'protected-capture'


def test_full_original_contracts_and_forged_context_rejected():
    value=json.loads((FIXTURE/'request.json').read_bytes());data=ProtectedData([FIXTURE]);validate=ContractData().validate
    assert validate_request(value,data,validate)['binding_id']
    for field in ('binding_id','role','policy_ref','inputs','invocation_limits'):
        changed=deepcopy(value);context=changed['selected_capsule']['bound_context']
        if field=='binding_id':context[field]='forged'
        elif field=='role':context[field]='verifier'
        elif field=='policy_ref':context[field]={'id':'forged','sha256':'0'*64}
        elif field=='inputs':context[field]=[]
        else:context[field]['model_calls']+=1
        with pytest.raises(IntegrityFault):validate_request(changed,data,validate)


@pytest.mark.parametrize('category',sorted(CATEGORIES))
def test_all_eight_source_categories(category):
    value=json.loads((FIXTURE/'request.json').read_bytes());value['task_category']=category
    assert validate_request(value,ProtectedData([FIXTURE]),ContractData().validate)


@pytest.mark.parametrize('field,value',[('domain','other'),('task_category','free_form'),('call_function','router')])
def test_unknown_domain_category_or_call_function_is_integrity_fault(field,value):
    request=json.loads((FIXTURE/'request.json').read_bytes());request[field]=value
    with pytest.raises(IntegrityFault):validate_request(request,ProtectedData([FIXTURE]),ContractData().validate)
