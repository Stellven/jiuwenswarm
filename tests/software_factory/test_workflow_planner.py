"""Planner protocol/admission tests. Scripted model replies are test-only."""
import json
from copy import deepcopy

import pytest

from jiuwenswarm.software_factory.contracts import StageBlocked, StageFailure
from jiuwenswarm.software_factory.workflow_library import WorkflowLibrary, admit_graph, _check_reused_source, digest
from jiuwenswarm.software_factory.workflow_planner import POLICY, WorkflowPlanner


def definition(name, parts):
    return {'id': name, 'name': name, 'source': {'repository': 'test-only:' + name},
            'subworkflows': [
                {'id': identity, 'name': identity, 'inputs': {k: {'semantic_type': v} for k,v in inputs.items()},
                 'outputs': {k: {'semantic_type': v} for k,v in outputs.items()},
                 'implementation': {'type': 'python',
                    'entrypoint': 'jiuwenswarm.software_factory.library_operations:report'}}
                for identity,inputs,outputs in parts]}


@pytest.fixture
def catalog(tmp_path):
    library=WorkflowLibrary(tmp_path/'library')
    a=library.register(definition('source', [('extract',{}, {'algorithm':'source.algorithm'}),
                                           ('report',{'algorithm':'source.algorithm'}, {'report':'analysis.report'})]))
    b=library.register(definition('engineering', [('generate',{'algorithm':'source.algorithm'}, {'cpp':'source.cpp'})]))
    return library,a,b


def node(identity, workflow, part, bindings=None):
    return {'id':identity,'workflow':{'id':workflow['id'],'version':workflow['version']},
            'subworkflow':part,'bindings':bindings or {}}


def graph(a,b):
    return {'nodes':[node('extract',a,'extract'),
            node('generate',b,'generate',{'algorithm':{'node':'extract','port':'algorithm'}})],
            'outputs':{'code':{'node':'generate','port':'cpp'}}}


class IsolatedResponseDriver:
    def __init__(self,*responses):
        self.responses=iter(responses);self.prompts=[]

    def run(self,prompt,workspace,**kwargs):
        assert kwargs['sandbox']=='read-only'
        self.prompts.append(prompt)
        return {'text':json.dumps(next(self.responses)),
                'invocation':{'driver':'isolated-test-driver','not_live_model_evidence':True}}


def test_tool_reads_precede_cross_workflow_graph_and_policy_is_saved(catalog,tmp_path):
    library,a,b=catalog
    reads={'tool_calls':[{'name':'library.read','arguments':{'workflow_id':w['id']}} for w in (a,b)]}
    proposal={'proposal':{'graph':graph(a,b),'decisions':[
        {'workflow_id':a['id'],'selected_parts':['extract'],'reason':'Need source evidence; omit optional report.'},
        {'workflow_id':b['id'],'selected_parts':['generate'],'reason':'Consume algorithm to produce required C++.'}]}}
    driver=IsolatedResponseDriver(reads,proposal)
    events=[]
    result=WorkflowPlanner(library,driver).plan(
        {'description':'Produce source','required_outputs':['source.cpp'],
         'acceptance':{'native_model_inference':True}},tmp_path/'plan',emit=lambda *e:events.append(e))
    assert len(result['graph']['nodes'])==2
    assert result['graph']['edges']==[{'from':'extract','to':'generate','output':'algorithm',
                                       'input':'algorithm','data':'source.algorithm'}]
    assert 'report' not in [n['subworkflow'] for n in result['graph']['nodes']]
    assert result['unmet_requirements'][0]['requirement']=='native_model_inference'
    assert (tmp_path/'plan'/'composer_policy.md').read_text()==POLICY
    assert [kind for kind,payload in events].count('planner.tool_finished')==2
    assert json.loads((tmp_path/'plan'/'planning.json').read_text())['invocations'][0]['not_live_model_evidence']


def test_malformed_tool_call_is_real_validation_feedback(catalog,tmp_path):
    library,a,b=catalog
    driver=IsolatedResponseDriver({'tool_calls':[{'name':'library.read','arguments':{}}]},
                            {'tool_calls':[{'name':'library.read','arguments':{'workflow_id':a['id']}}]},
                            {'proposal':{'graph':{'nodes':[node('source',a,'extract')],
                                         'outputs':{'algorithm':{'node':'source','port':'algorithm'}}},
                                         'decisions':[{'workflow_id':a['id'],'selected_parts':['extract'],
                                                       'reason':'Only extraction is requested.'}]}})
    result=WorkflowPlanner(library,driver).plan(
        {'description':'Extract only','required_outputs':['source.algorithm']},tmp_path/'plan')
    assert len(result['graph']['nodes'])==1
    assert 'validation_defect' in driver.prompts[1]


@pytest.mark.parametrize('case,code',[
    ('version','invalid_graph'),('arbitrary_executor','invalid_graph'),
    ('wrong_port','unknown_output'),('wrong_type','incompatible_artifact'),
    ('missing_goal','uncovered_deliverables'),('external_path','invalid_graph')])
def test_graph_admission_rejects_unexecutable_proposals(catalog,case,code):
    library,a,b=catalog
    value=graph(a,b)
    if case=='version':value['nodes'][0]['workflow']['version']='latest'
    elif case=='arbitrary_executor':value['nodes'][0]['executor']='subprocess:run'
    elif case=='wrong_port':value['nodes'][1]['bindings']['algorithm']['port']='missing'
    elif case=='wrong_type':
        value['nodes']=[node('report',a,'report',{'algorithm':{'node':'gen','port':'cpp'}}),
                        node('gen',b,'generate',{'algorithm':{'node':'extract','port':'algorithm'}}),node('extract',a,'extract')]
    elif case=='missing_goal':value['outputs']={'wrong':{'node':'extract','port':'algorithm'}}
    elif case=='external_path':value['inputs']={'file':{'path':'/etc/passwd'}}
    with pytest.raises(StageFailure) as caught:
        admit_graph(library,{'graph':value},{'required_outputs':['source.cpp']})
    assert caught.value.code==code


def test_actual_model_unavailability_never_falls_back_to_prebuilt_graph(catalog,tmp_path):
    library,a,b=catalog
    class Unavailable:
        def run(self,*args,**kwargs):
            raise StageBlocked('model_execution_failed','actual provider failed',{'invocation':{'exit_code':1}})
    with pytest.raises(StageBlocked) as error:
        WorkflowPlanner(library,Unavailable()).plan(
            {'description':'Produce C++','required_outputs':['source.cpp']},tmp_path/'plan')
    assert error.value.details['invocation']['exit_code']==1
    assert not (tmp_path/'plan'/'graph.json').exists()


def test_unread_parts_cannot_be_selected(catalog,tmp_path):
    library,a,b=catalog
    driver=IsolatedResponseDriver({'proposal':{'graph':graph(a,b),'decisions':[
        {'workflow_id':w['id'],'selected_parts':['extract','generate'],'reason':'test reason'} for w in (a,b)]}})
    with pytest.raises(StageFailure,match='budget'):
        WorkflowPlanner(library,driver).plan(
            {'description':'C++','required_outputs':['source.cpp']},tmp_path/'plan',max_turns=1)


def test_decision_cannot_claim_unused_sibling_was_selected(catalog, tmp_path):
    library, source, engineering = catalog
    reads = {'tool_calls': [{'name': 'library.read', 'arguments': {'workflow_id': item['id']}}
                            for item in (source, engineering)]}
    proposal = {'proposal': {'graph': graph(source, engineering), 'decisions': [
        {'workflow_id': source['id'], 'selected_parts': ['extract', 'report'],
         'reason': 'Claim both parts were picked.'},
        {'workflow_id': engineering['id'], 'selected_parts': ['generate'], 'reason': 'Write source.'},
    ]}}
    events = []
    with pytest.raises(StageFailure, match='budget'):
        WorkflowPlanner(library, IsolatedResponseDriver(reads, proposal)).plan(
            {'description': 'Produce C++', 'required_outputs': ['source.cpp']}, tmp_path / 'plan',
            max_turns=2, emit=lambda *event: events.append(event),
        )
    assert any(kind == 'planner.proposal_rejected' and payload['code'] == 'inconsistent_decision'
               for kind, payload in events)


def test_replanning_reads_real_execution_feedback_and_keeps_previous_graph(catalog,tmp_path):
    library,a,b=catalog
    driver=IsolatedResponseDriver(
        {'tool_calls':[{'name':'library.read','arguments':{'workflow_id':a['id']}}]},
        {'proposal':{'graph':{'nodes':[node('extract',a,'extract')],
                             'outputs':{'algorithm':{'node':'extract','port':'algorithm'}}},
                     'decisions':[{'workflow_id':a['id'],'selected_parts':['extract'],
                                   'reason':'The earlier producer failed; use the available source extraction.'}]}})
    feedback={'id':'prior-execution','status':'failed','graph':{'graph_revision':2},'nodes':[
        {'id':'earlier','status':'failed','error':{'message':'actual missing header'},'attempts':[
            {'commands':[{'argv':['c++','source.cpp'],'exit_code':1,'stderr':'fatal error: missing.h'}]}]}]}
    original=deepcopy(feedback)
    result=WorkflowPlanner(library,driver).plan(
        {'description':'Extract again','required_outputs':['source.algorithm']},tmp_path/'plan',feedback=feedback)
    assert 'actual missing header' in driver.prompts[0]
    assert 'fatal error: missing.h' in driver.prompts[0]
    assert result['graph']['graph_revision']==3
    assert result['graph']['previous_execution_ref']=='prior-execution'
    assert feedback==original
    assert json.loads((tmp_path/'plan'/'previous_execution.json').read_text())==original


def test_reused_source_must_contain_required_operation_and_commit(tmp_path):
    """Minimal isolated content fixture, not algorithm/migration acceptance."""
    path=tmp_path/'ir.json'
    value={'schema':'strata.core.ir.v1','selected':['routing-source'],
           'commit_sha':'a'*40,'kernels':{'routing-source':{'id':'routing-source','category':'routing','operation':'router'}}}
    path.write_text(json.dumps(value))
    artifact={'kind':'source.algorithm','path':str(path),'sha256':digest(path.read_bytes())}
    with pytest.raises(StageFailure) as caught:
        _check_reused_source(artifact,{'parameters':{'operations':['normalization']}})
    assert caught.value.code=='task_operation_mismatch'
    with pytest.raises(StageFailure) as caught:
        _check_reused_source(artifact,{'source':{'revision':'b'*40}})
    assert caught.value.code=='task_revision_mismatch'
    _check_reused_source(artifact,{'parameters':{'operations':['routing']},'source':{'revision':'a'*40}})


def test_null_unmet_requirements_is_feedback_not_unhandled_exception(catalog,tmp_path):
    library,a,b=catalog
    driver=IsolatedResponseDriver(
        {'tool_calls':[{'name':'library.read','arguments':{'workflow_id':w['id']}} for w in (a,b)]},
        {'proposal':{'graph':graph(a,b),'unmet_requirements':None,'decisions':[
            {'workflow_id':a['id'],'selected_parts':['extract'],'reason':'source'},
            {'workflow_id':b['id'],'selected_parts':['generate'],'reason':'code'}]}})
    events=[]
    with pytest.raises(StageFailure,match='budget'):
        WorkflowPlanner(library,driver).plan(
            {'description':'C++','required_outputs':['source.cpp'],'acceptance':{'native_compile':True}},
            tmp_path/'plan',emit=lambda *event:events.append(event),max_turns=2)
    assert any(kind=='planner.proposal_rejected' and payload['code']=='invalid_unmet_requirements'
               for kind,payload in events)
