"""Minimized public projection controls; no publication or qualification occurs."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest

from jiuwenswarm.research_rsi.calibration import prepare_calibration_plan
from jiuwenswarm.research_rsi.calibration_materials import prepare_calibration_materials, PROVENANCE_SCHEMA
from jiuwenswarm.research_rsi.candidate_bindings import CandidateResolver, binding_id
from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_records.contracts import ContractData
from jiuwenswarm.research.contracts.rsi_security import RSIQualification


def test_public_provenance_contract_excludes_private_refs_and_generated_model_claims():
    pin={'id':'unit:public-pin','sha256':'a'*64}
    value=dict(schema='ai4r-rsi-calibration-material-provenance:1',purpose='PLANTED_CALIBRATION_CONTROL',
        generator_source_sha256='b'*64,materializer_source_sha256='c'*64,plan_sha256='d'*64,
        source_sha256='e'*64,session_ref=pin,target_ref=pin,parent_declaration_ref=pin,generating_model=None)
    validate=ContractData().validate;validate(PROVENANCE_SCHEMA,value)
    for changed in (dict(value,plan_ref=pin),dict(value,preparation_ref=pin),dict(value,private_seed='forbidden'),
                    dict(value,generating_model='fake-model'),dict(value,fixture_identity='forbidden')):
        with pytest.raises(ValueError):validate(PROVENANCE_SCHEMA,changed)


def test_material_projection_refuses_non_custodian_without_publication(tmp_path):
    store=RecordStore(tmp_path)
    if sys.platform=='linux' and os.geteuid()==12002:os.chmod(tmp_path,0o755)
    with pytest.raises(ValueError):
        prepare_calibration_materials(store,plan_ref={},approved_plan_refs=[],parent_body_refs={})
    assert not list(tmp_path.rglob('original-byte-index.json'))
    store.close()


def controlled_materials_main(root):
    import shutil
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.capsules.assets import build_research_assets
    from jiuwenswarm.research_rsi.targets import ranking_preparation
    from tests.unit_tests.research_rsi.test_calibration_collection import _scope
    os.setgid(12002);os.setuid(12002);os.umask(0o077)
    store=RecordStore(root/'store');core=SQLiteRunStore(root/'public-parent-capture')
    try:
        base=_scope(store,seed='unit:materials-private-seed-001')
        asset=build_research_assets(core,verify_catalog=False)['screening']
        parent=core.read_record(asset['declaration_ref'])
        declared_paths={row['path'] for row in parent['identity']['body']}
        body_refs={path:store.put_bytes(core.read_blob(pin)) for path,pin in asset['body_refs'].items() if path in declared_paths}
        parent_ref=body_refs['ranking_parent.txt'];decl_ref=store.put(parent)
        origin=store.put({'unit':'Public-material projection mechanics; not independent operational approval'})
        generator=store.put_bytes(Path(ranking_preparation.__file__).read_bytes())
        prep_ref=ranking_preparation.prepare_ranking(store,parent_ref=parent_ref,parent_declaration_ref=decl_ref,
            declaration=parent,author='unit:material-author',origin_ref=origin,generator_ref=generator,
            populations=dict(development=1,hidden_loop=20,hidden_final=20,platform=3),seed='unit:materials-private-seed-002')
        review=store.get(base['review_ref']);review['preparation_ref']=prep_ref
        review['evidence_refs']=[origin];review_ref=store.put(review)
        target,manifest=ranking_preparation.draft_target(store,prep_ref,store.get(base['target_ref']),
            review_ref=review_ref,validate=ContractData().validate)
        target_ref=store.put(target);manifest['target_ref']=target_ref;manifest_ref=store.put(manifest)
        session=store.get(base['session_ref'])
        session.update(target_profile_ref=target_ref,parent_declaration_ref=decl_ref,
            parent=dict(cc_name=parent['identity']['name'],cc_version=parent['identity']['version_label'],declaration_sha256=decl_ref['sha256']))
        session_ref=store.put(session)
        profile=store.get(base['worker_profile_ref']);profile.update(target_ref=target_ref,session_ref=session_ref,parent_ref=parent_ref)
        worker_ref=store.put(profile)
        refs=dict(preparation_ref=prep_ref,review_ref=review_ref,target_ref=target_ref,fixture_manifest_ref=manifest_ref,
                  session_ref=session_ref,worker_profile_ref=worker_ref)
        plan_ref=prepare_calibration_plan(store,**refs,invocation_wall_s=.5,evidence_wall_s=1,wall_s=3600)
        prep=store.get(prep_ref);secret=store.put_bytes(b'unit-private-key-sentinel-never-projected')
        candidates=[row['body_ref'] for row in prep['children']]
        try:prepare_calibration_materials(store,plan_ref=plan_ref,approved_plan_refs=[],parent_body_refs=body_refs)
        except ValueError:pass
        else:raise AssertionError('Unapproved projection accepted')
        assert all(store.candidate_binding_ref(session_ref,pin) is None for pin in candidates)
        for changed in ({**body_refs,'private-fixture.json':secret},
                        {path:pin for path,pin in body_refs.items() if path!='ranking_parent.txt'},
                        dict(body_refs,ranking_parent=secret),dict(body_refs,**{'ranking_parent.txt':secret})):
            try:prepare_calibration_materials(store,plan_ref=plan_ref,approved_plan_refs=[plan_ref],parent_body_refs=changed)
            except ValueError:pass
            else:raise AssertionError('Open-ended or altered parent closure accepted')
        assert all(store.candidate_binding_ref(session_ref,pin) is None for pin in candidates)
        projection=prepare_calibration_materials(store,plan_ref=plan_ref,approved_plan_refs=[plan_ref],parent_body_refs=body_refs)
        assert projection==prepare_calibration_materials(store,plan_ref=plan_ref,approved_plan_refs=[plan_ref],parent_body_refs=body_refs)
        indexed={item['ref']['id']:item for item in projection}
        assert len(indexed)==len(projection)==4+len(body_refs)+13*5
        assert all(set(item)=={'ref','bytes'} and hashlib.sha256(item['bytes']).hexdigest()==item['ref']['sha256'] for item in projection)
        required=[session_ref,target_ref,worker_ref,decl_ref,*body_refs.values()]
        assert all(indexed[pin['id']]['bytes']==store.read(pin) for pin in required)
        forbidden=[prep_ref,review_ref,plan_ref,manifest_ref,origin,generator,store.get(plan_ref)['collector_ref'],secret]
        forbidden.extend(pin for rows in prep['partitions'].values() for row in rows for pin in (row['input_ref'],row['expected_ref']))
        assert all(pin['id'] not in indexed for pin in forbidden)
        raw=b'\n'.join(item['bytes'] for item in projection)
        assert prep['private_seed'].encode() not in raw and b'unit-private-key-sentinel-never-projected' not in raw
        assert str(root).encode() not in raw
        assert all(row['id'].encode() not in raw for rows in prep['partitions'].values() for row in rows)
        def read_public(pin):
            item=indexed[pin['id']]
            assert item['ref']['sha256']==pin['sha256']
            return item['bytes']
        def locate(session_pin,candidate):
            return indexed[binding_id(session_pin,candidate)]['ref']
        resolver=CandidateResolver(read=read_public,locate=locate)
        versions=set()
        for candidate in candidates:
            binding_ref=store.candidate_binding_ref(session_ref,candidate)
            alias=binding_id(session_ref,candidate)
            assert indexed[alias]['bytes']==indexed[binding_ref['id']]['bytes']
            binding=json.loads(indexed[alias]['bytes']);child_ref=binding['declaration_ref']
            assert resolver(session_ref,candidate)==child_ref
            child=json.loads(read_public(child_ref));lineage=child['identity']['lineage']
            assert lineage['parent']==decl_ref and lineage['build_trigger']==session['session_id']
            assert lineage['builder']=='rsi_workbench' and lineage['provenance']['generating_model'] is None
            provenance=json.loads(read_public(lineage['builder_ref']))
            ContractData().validate(PROVENANCE_SCHEMA,provenance)
            assert provenance['plan_sha256']==plan_ref['sha256'] and provenance['source_sha256']==candidate['sha256']
            assert provenance['generator_source_sha256']==generator['sha256']
            assert set(provenance)=={'schema','purpose','generator_source_sha256','materializer_source_sha256',
                'plan_sha256','source_sha256','session_ref','target_ref','parent_declaration_ref','generating_model'}
            before=copy.deepcopy(parent);after=copy.deepcopy(child)
            for value in (before,after):
                for key in ('version_label','body','lineage'):value['identity'].pop(key,None)
            assert before==after
            versions.add(child['identity']['version_label'])
        assert len(versions)==13
        guard=RSIQualification(read_public,None,candidate_resolver=resolver)
        assert guard._subject('trial',session_ref,candidates[0])==session
        try:guard.require('trial',session_ref=session_ref,candidate_ref=candidates[0])
        except ValueError:pass
        else:raise AssertionError('Material bindings granted security qualification')
        assert not (store.root/'calibration.sqlite').exists()
        assert not list(root.rglob('original-byte-index.json'))
    finally:
        core.close();store.close();shutil.rmtree(root)


def test_actual_linux_custodian_projection_is_minimized_deterministic_and_binding_complete():
    if sys.platform!='linux' or os.geteuid()!=0:
        assert sys.platform!='linux' or os.geteuid()!=0
        return
    root=Path(tempfile.mkdtemp(prefix='rsi-materials-control-',dir='/dev/shm'))
    os.chmod(root,0o700);os.chown(root,12002,12002)
    program='from pathlib import Path; import sys; from tests.unit_tests.research_rsi.test_calibration_materials import controlled_materials_main; controlled_materials_main(Path(sys.argv[1]))'
    completed=subprocess.run([sys.executable,'-B','-c',program,str(root)],capture_output=True,text=True,timeout=120)
    assert completed.returncode==0,completed.stderr
    assert completed.stdout=='' and not root.exists()
