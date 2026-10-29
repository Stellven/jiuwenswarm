"""Controlled manifests/probes test fail-closed composition, not qualification."""
import hashlib
import json
import os
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.contracts import Principal,ResearchError
from jiuwenswarm.research.native_ports import NativePorts,verify_installed_build


def installed_manifest(tmp_path):
    package=tmp_path/'installed';package.mkdir();(package/'module.py').write_bytes(b'# exact installed candidate\n')
    tui=tmp_path/'installed_tui';tui.mkdir();(tui/'app.py').write_bytes(b'# exact separate TUI component\n');tui_raw=(tui/'app.py').read_bytes()
    raw=(package/'module.py').read_bytes()
    body={'schema':'ai4r-installed-build:2','links':[],'files':[{'path':'module.py','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}],
          'components':{'jiuwenswarm_tui':{'links':[],'files':[{'path':'app.py','bytes':len(tui_raw),'sha256':hashlib.sha256(tui_raw).hexdigest()}]}},
          'dependencies':[],'uv_lock_sha256':'a'*64,'pyproject_sha256':'b'*64}
    body['build_id']=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    manifest=tmp_path/'build.json';manifest.write_text(json.dumps(body));manifest.chmod(0o644)
    return manifest,package,body['build_id']


def test_build_identity_checks_original_installed_bytes(tmp_path):
    manifest,package,build=installed_manifest(tmp_path)
    assert verify_installed_build(manifest,package_root=package,component_roots={'jiuwenswarm_tui':tmp_path/'installed_tui'})==build
    (package/'module.py').write_bytes(b'# altered installation\n')
    with pytest.raises(ResearchError,match='installed_build_invalid'):verify_installed_build(manifest,package_root=package,component_roots={'jiuwenswarm_tui':tmp_path/'installed_tui'})


def test_build_identity_allows_only_exact_relative_internal_link_closure(tmp_path):
    manifest,package,build=installed_manifest(tmp_path)
    (package/'alias.py').symlink_to('module.py')
    value=json.loads(manifest.read_text());value['links']=[{'path':'alias.py','target':'module.py'}]
    value.pop('build_id');value['build_id']=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    manifest.write_text(json.dumps(value))
    assert verify_installed_build(manifest,package_root=package,component_roots={'jiuwenswarm_tui':tmp_path/'installed_tui'})==value['build_id']
    (package/'extra.py').symlink_to('module.py')
    with pytest.raises(ResearchError,match='installed_build_invalid'):verify_installed_build(manifest,package_root=package,component_roots={'jiuwenswarm_tui':tmp_path/'installed_tui'})
    (package/'extra.py').unlink();(package/'alias.py').unlink();(package/'alias.py').symlink_to('../outside.py')
    (tmp_path/'outside.py').write_text('# outside installed package')
    with pytest.raises(ResearchError,match='installed_build_invalid'):verify_installed_build(manifest,package_root=package,component_roots={'jiuwenswarm_tui':tmp_path/'installed_tui'})


@pytest.mark.asyncio
async def test_builder_unqualified_and_captured_build_mismatch_never_report_ready(tmp_path):
    from tests.unit_tests.research.test_budget_ceiling import installed_library
    manifest,package,build=installed_manifest(tmp_path);ipc=tmp_path/'ipc';ipc.mkdir(mode=0o700)
    session=ipc/'session.json';session.write_text(json.dumps({'session_id':'fixture','capability':'controlled-test-capability'}));session.chmod(0o600)
    ports=NativePorts(ipc_root=ipc,app_uid=os.geteuid(),build_manifest=manifest,installed_package_root=package,installed_component_roots={'jiuwenswarm_tui':tmp_path/'installed_tui'})
    store,_,_,library,_,_=await installed_library(tmp_path/'state')
    ref=store.put_record('plan-policy',json.loads(__import__('pathlib').Path('tests/fixtures/research/planning/plan_policy.json').read_bytes()))
    composition=SimpleNamespace(library=library,compiler=object(),scheduler=object(),diagnostics=[])
    operator=SimpleNamespace(snapshot=lambda:{'cc':{'plan_policy_ref':ref,'router':{'enabled':False}}})
    await ports.bind_composition(composition,{'build_id':build,'instance_id':'fixture-instance','protected_options':{}},operator)
    async def ready_subscription(*a,**kw):return {'state':'ready','enabled':True,'builder_qualified':False}
    ports.status_client=SimpleNamespace(call=ready_subscription);ports.executor=SimpleNamespace(prerequisites=lambda:[])
    actor=Principal('alice',operations=frozenset({'readiness'}))
    value=await ports.readiness(actor)
    assert value['ready'] is False and next(p for p in value['prerequisites'] if p['name']=='builder')['status']=='unavailable'
    ports.bindings['build_id']='f'*64
    value=await ports.readiness(actor)
    assert value['ready'] is False and value['build_id']==build
    assert next(p for p in value['prerequisites'] if p['name']=='build_identity')['status']=='unavailable'
    store.close()


def test_v2_checks_separate_tui_bytes_and_v1_requires_explicit_fixture_opt_in(tmp_path):
    manifest,package,build=installed_manifest(tmp_path);roots={'jiuwenswarm_tui':tmp_path/'installed_tui'}
    (roots['jiuwenswarm_tui']/'app.py').write_bytes(b'# changed TUI\n')
    with pytest.raises(ResearchError):verify_installed_build(manifest,package_root=package,component_roots=roots)
    value=json.loads(manifest.read_bytes());value.pop('components');value['schema']='ai4r-installed-build:1';value.pop('build_id')
    value['build_id']=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest();manifest.write_text(json.dumps(value))
    with pytest.raises(ResearchError):verify_installed_build(manifest,package_root=package)
    assert verify_installed_build(manifest,package_root=package,allow_legacy_fixture=True)==value['build_id']


@pytest.mark.asyncio
async def test_missing_canonical_pins_returns_explicit_unavailable_without_forging_run_pins(tmp_path):
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    from jiuwenswarm.research.state import SQLiteRunStore
    from tests.unit_tests.research.test_operator_config import valid_config
    manifest,package,build=installed_manifest(tmp_path);ipc=tmp_path/'ipc';ipc.mkdir(mode=0o700)
    (ipc/'session.json').write_text(json.dumps({'session_id':'actual-fixture-boot','capability':'controlled-capability'}))
    (ipc/'session.json').chmod(0o600)
    ports=NativePorts(ipc_root=ipc,app_uid=os.geteuid(),build_manifest=manifest,installed_package_root=package,
        installed_component_roots={'jiuwenswarm_tui':tmp_path/'installed_tui'})
    store=SQLiteRunStore(tmp_path/'state');operator=OperatorConfiguration.from_mapping(valid_config())
    await ports.bind_inspection(store,operator,[{'code':'bootstrap_unavailable','detail':'Protected bootstrap bindings are missing'}])
    async def absent(*args,**kwargs):raise OSError('controlled missing native process')
    ports.status_client=SimpleNamespace(call=absent);ports.executor=SimpleNamespace(prerequisites=lambda:{'ready':False,'builder_qualified':False,'reasons':['controlled unavailable']})
    actor=Principal('alice',operations=frozenset({'readiness'}))
    with pytest.raises(ResearchError,match='canonical selectable library snapshot'):
        await ports.readiness(actor)
    assert len(list(store.iter_records(kinds=('library-admission','activation-record'))))==0
    assert not list(store.iter_records(kinds=('library-snapshot',)))
    snapshots=list(store.iter_records(kinds=('library-eligibility-observation',)))
    assert len(snapshots)==1 and snapshots[0]['record']['entries']==[]
    assert snapshots[0]['record']['reason_code']=='no_eligible_capsule'
    with pytest.raises(ResearchError):await ports.readiness(actor)
    assert len(list(store.iter_records(kinds=('library-eligibility-observation',))))==1
    store.close()
