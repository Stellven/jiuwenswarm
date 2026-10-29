"""Public metadata assembly boundaries; no native/model/executor service."""
import importlib.util
import json
from pathlib import Path

import pytest

PATH=Path(__file__).parents[3]/'deploy/m1/rsi_development_prepare.py'
spec=importlib.util.spec_from_file_location('unit_development_prepare',PATH)
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


def material(text,ident):
    raw=text.encode();return {'id':ident,'sha256':p.seed.digest(raw)},raw


def test_public_documents_preserve_opaque_refs_bytes_and_honest_deferred_context():
    first=material('def helper(): return 3\n','opaque-body')
    second=material('{"public_input":1}','opaque-visible')
    docs=p.public_documents({'one':first,'two':second},'Inspect redundant computation; no gain established.')
    context=json.loads(docs['development-context.txt'])
    assert context['security_campaigns']=='DEFERRED' and context['qualification'] is False
    assert context['originals']==[{'ref':first[0],'utf8':first[1].decode()},{'ref':second[0],'utf8':second[1].decode()}]
    assert context['originals'][0]['utf8'].encode()==first[1]
    assert len(docs)==1 and not any('hidden' in name or 'auth' in name for name in docs)


def test_same_bytes_aliases_keep_both_provenances_without_duplicate_uploads():
    one=material('same public source','opaque-one');two=material('same public source','opaque-two')
    docs=p.public_documents({'one':one,'two':two},'Public request')
    assert len(docs)==1
    assert [row['ref']['id'] for row in json.loads(docs['development-context.txt'])['originals']]==['opaque-one','opaque-two']


def test_actual_72_material_schedule_uses_one_upload_and_fits_96_original_refs():
    materials={str(i):material('public original '+str(i),'opaque-'+str(i)) for i in range(72)}
    documents=p.public_documents(materials,'No performance gain established; inspect public computation.')
    assert len(documents)==1 and len(json.loads(next(iter(documents.values())))['originals'])==72
    assert p.public_closure_bound(materials,'No performance gain established; inspect public computation.')==75
    corpus=material('labeled checking object','checking-origin')[0]
    p.reject_checking_corpus(materials,[corpus])
    aliased={'id':'public-looking-alias','sha256':corpus['sha256']}
    with pytest.raises(ValueError,match='CHECKING_CORPUS'):
        p.reject_checking_corpus(materials|{'extra':(aliased,b'labeled checking object')},[corpus])
    excessive={str(i):material('public '+str(i),'opaque-'+str(i)) for i in range(96)}
    with pytest.raises(ValueError,match='AUTHORIZATION_BOUND'):p.public_closure_bound(excessive,'request')


def test_invalid_or_oversized_public_bytes_refused_before_metadata_claim():
    with pytest.raises(UnicodeError):p.public_documents({'binary':({'id':'x','sha256':'a'*64},b'\xff')},'request')
    with pytest.raises(ValueError):p.public_documents({'large':material('x'*(4*1024*1024),'large')},'request')


def test_root_claim_path_is_outside_uid12001_mutable_namespace():
    source=PATH.read_text(encoding='utf8')
    assert "Path(input_path).with_name('claim.json')" in source
    assert "seed.exclusive(output.with_suffix('.claim.json')" not in source
    assert 'METADATA_PREPARATION_HAS_NO_MODEL_OR_EXECUTION_AUTHORITY' in source


def test_direct_intake_upload_and_operator_source_changes_change_review_facts(tmp_path,monkeypatch):
    from jiuwenswarm.research import uploads,intake,operator_config
    for index,module in enumerate((uploads,intake,operator_config)):
        path=tmp_path/('source-'+str(index)+'.py');path.write_bytes(b'# original intake implementation\n')
        monkeypatch.setattr(module,'__file__',str(path))
        before=p.intake_source_pins()
        path.write_bytes(b'# changed intake implementation\n')
        after=p.intake_source_pins()
        assert before[module.__name__]!=after[module.__name__]
        assert p.seed.digest(p.seed.encoded(before))!=p.seed.digest(p.seed.encoded(after))


@pytest.mark.parametrize('fault',[None,'missing-host','blank-host','extra','workspace'])
def test_actual_six_key_host_binding_projects_canonical_five_without_losing_provenance(fault):
    binding={'configuration_ref':{'id':'config','sha256':'a'*64},'model_selection_profile_ref':{'id':'selection','sha256':'b'*64},
        'deployment_ref':{'id':'deployment','sha256':'c'*64},'workspace_id':'local',
        'protected_options':{'development_builtin_catalog':False},'host_id':'original-host'}
    if fault=='missing-host':del binding['host_id']
    elif fault=='blank-host':binding['host_id']=''
    elif fault=='extra':binding['browser_authority']=True
    elif fault=='workspace':binding['workspace_id']='foreign'
    if fault:
        with pytest.raises(ValueError):p.project_host_binding(binding,'local')
    else:
        exact,host=p.project_host_binding(binding,'local')
        assert len(exact)==5 and host=='original-host' and dict(exact,host_id=host)==binding
