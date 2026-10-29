"""Multi-generation Root metadata only; no live namespace/runtime effects."""
import copy
import os
from pathlib import Path
import sqlite3
import pytest
from tests.unit_tests.scripts.test_rsi_bootstrap_supersession import s,context,completed_fixture,next_request,pin

ROOT=pytest.mark.skipif(os.name!='posix' or os.geteuid()!=0,reason='Root archive custody')

def generation_context(generation,identity):
    request,original,selected,*_=copy.deepcopy(context())
    request.update(generation=generation,supersession_id=identity,fresh_profile_generation=generation+'-fresh')
    original['generation']=selected['generation']=generation
    original['root']=selected['root']='/own/controller.'+generation
    original['profile_generations']={stage:generation for stage in original['profile_generations']}
    selected['profile_generations']={**original['profile_generations'],'planner':request['fresh_profile_generation']}
    return request,original,selected


@ROOT
@pytest.mark.parametrize('fault',[None,'foreign-partial','foreign-tamper','cross-generation','duplicate-identity','branch'])
def test_disjoint_generation_chains_preserve_all_originals_and_never_skip_foreign_faults(tmp_path,fault):
    (tmp_path/'config').mkdir();parent=tmp_path/'config/bootstrap-supersessions';s.mkdir(parent)
    a,base_a,selected_a=generation_context('run-one','capacity-one')
    first=completed_fixture(parent/'run-one',a,base_a,selected_a)
    successor=next_request(first,parent/'run-one')
    second=copy.deepcopy(selected_a);second['profile_generations']['verifier']=successor['fresh_profile_generation']
    second['stages'][0]['profile_ref']=pin('fresh-verifier');second['calibration_runtime_ref']=pin('second-runtime')
    completed_fixture(parent/successor['supersession_id'],successor,base_a,second,parent/'run-one')
    before={str(path.relative_to(parent)):path.read_bytes() for path in parent.rglob('*') if path.is_file()}
    b,base_b,selected_b=generation_context('run-two','capacity-three')
    b.update(schema='ai4r-rsi-bootstrap-supersession-input:2',predecessor=None,budget_caps={'pre_delivery':68,'setup':75,'including_rsi':77})
    completed_fixture(parent/'run-two',b,base_b,selected_b)
    if fault=='foreign-partial':(parent/'run-one/complete.json').unlink()
    if fault=='foreign-tamper':
        path=parent/'run-one/plan.json';path.chmod(0o600);path.write_bytes(b'{}');path.chmod(0o440)
    if fault=='cross-generation':
        bad=next_request(first,parent/'run-one');bad.update(generation='run-two',supersession_id='cross-generation')
        completed_fixture(parent/'cross-generation',bad,base_a,second,parent/'run-one')
    if fault=='duplicate-identity':
        c,base_c,selected_c=generation_context('run-three','capacity-one')
        completed_fixture(parent/'run-three',c,base_c,selected_c)
    if fault=='branch':
        bad=copy.deepcopy(successor);bad['supersession_id']='branch'
        completed_fixture(parent/'branch',bad,base_a,second,parent/'run-one')
    if fault:
        with pytest.raises((ValueError,KeyError,FileNotFoundError)):s.issued_chain(tmp_path,generation='run-two')
    else:
        s.verify_deployment_selections(tmp_path)
        assert {key:len(value) for key,value in s.issued_chains(tmp_path).items()}=={'run-one':2,'run-two':1}
        assert len(s.issued_chain(tmp_path,generation='run-one'))==2
        assert len(s.issued_chain(tmp_path,generation='run-two'))==1
        with pytest.raises(ValueError,match='EXPLICIT_BOOTSTRAP'):s.issued_chain(tmp_path)
        assert s.predecessor(base_b,b,[])==base_b
        with pytest.raises(ValueError,match='ONLY_ONE_ROOT_INITIAL'):s.predecessor(base_b,b,s.issued_chain(tmp_path,generation='run-two'))
        assert all((parent/name).read_bytes()==raw for name,raw in before.items())


def test_explicit_v2_initial_root_supports_four_charged_calls_without_widening_v1():
    item,original,selected=generation_context('run-two','capacity-four')
    item.update(schema='ai4r-rsi-bootstrap-supersession-input:2',predecessor=None,budget_caps={'pre_delivery':68,'setup':75,'including_rsi':77})
    s.validate_input(item)
    assert s.target_path(Path('/unit'),item)==Path('/unit/config/bootstrap-supersessions/run-two')
    legacy=dict(item,schema='ai4r-rsi-bootstrap-supersession-input:1');legacy.pop('predecessor')
    with pytest.raises(ValueError,match='BOUNDED'):s.validate_input(legacy)


def test_source_pins_include_actual_imported_native_completion_decoder_bytes(tmp_path,monkeypatch):
    from jiuwenswarm.research_rsi import native_lease
    source=tmp_path/'native_lease.py';source.write_bytes(b'unit initial decoder bytes')
    monkeypatch.setattr(native_lease,'__file__',str(source))
    before=s.source_pins();assert before['native_lease.py']==s.digest(source.read_bytes())
    source.write_bytes(b'unit changed decoder bytes')
    after=s.source_pins();assert before['native_lease.py']!=after['native_lease.py']
    assert {k:v for k,v in before.items() if k!='native_lease.py'}=={k:v for k,v in after.items() if k!='native_lease.py'}


@ROOT
def test_registry_has_finite_global_bound_before_reading_any_entries(tmp_path,monkeypatch):
    (tmp_path/'config').mkdir();parent=tmp_path/'config/bootstrap-supersessions';s.mkdir(parent)
    for index in range(129):s.mkdir(parent/('entry-'+str(index)))
    monkeypatch.setattr(s,'selection_chain',lambda path:pytest.fail('Overfull registry must fail before any chain read'))
    with pytest.raises(ValueError,match='REGISTRY'):s.issued_chains(tmp_path)


def namespace(path,state='complete'):
    path.mkdir(mode=0o700);os.chown(path,12001,12001)
    for relative in ('native-leases','core','core/state'):
        current=path/relative;current.mkdir(mode=0o700);os.chown(current,12001,12001)
    (path/'bootstrap.json').write_bytes(b'{"unit":"immutable original"}')
    db=sqlite3.connect(path/'native-leases/index.sqlite')
    db.execute('CREATE TABLE native_effect_leases(scope TEXT PRIMARY KEY,state TEXT,ref TEXT)')
    db.execute('INSERT INTO native_effect_leases VALUES(?,?,?)',('unit-scope',state,'{}'));db.commit();db.close()
    core=sqlite3.connect(path/'core/state/research.sqlite3');core.execute('CREATE TABLE originals(value TEXT)');core.execute("INSERT INTO originals VALUES('unchanged')");core.commit();core.close()
    for relative in ('bootstrap.json','native-leases/index.sqlite','core/state/research.sqlite3'):
        current=path/relative;current.chmod(0o600);os.chown(current,12001,12001)


@ROOT
@pytest.mark.parametrize('fault',[None,'active','uncertain','extra-namespace','foreign-history'])
def test_foreign_original_namespaces_must_remain_complete_preserved_and_fully_rejoined(tmp_path,monkeypatch,fault):
    controller=tmp_path/'controller';controller.mkdir()
    namespace(controller/'operational-bootstrap.run-one',fault if fault in ('active','uncertain') else 'complete')
    namespace(controller/'operational-bootstrap.run-two')
    if fault=='extra-namespace':namespace(controller/'operational-bootstrap.unknown')
    before={str(path):path.read_bytes() for path in controller.rglob('*') if path.is_file()}
    monkeypatch.setattr(s,'issued_chains',lambda *args,**kwargs:{'run-one':['Root-completed-chain']})
    calls=[]
    def historical(root,generation,**kwargs):
        calls.append(generation)
        if fault=='foreign-history':raise ValueError('TAMPERED_FOREIGN_HISTORY')
        return {'failed_refs':[pin('historical-failed')],'historical_extra_model_calls':4}
    monkeypatch.setattr(s,'historical_capacity_dispositions',historical)
    if fault:
        with pytest.raises(ValueError):s.foreign_namespace_facts(tmp_path,'run-two',{'prior_namespaces':['run-one']})
    else:
        result=s.foreign_namespace_facts(tmp_path,'run-two',{'prior_namespaces':['run-one']})
        assert calls==['run-one'] and result[0]['native_states']=={'complete':1}
        assert result[0]['completed_capacity_dispositions']['historical_extra_model_calls']==4
    assert {str(path):path.read_bytes() for path in controller.rglob('*') if path.is_file()}==before
