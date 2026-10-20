"""Real native CLI and OS operator; visible fixtures never imply readiness."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest
import yaml

from jiuwenswarm.research.state import SQLiteRunStore
from tests.unit_tests.research.test_operator_config import valid_config


@pytest.mark.skipif(os.name!='posix',reason='Actual Linux OS operator is required')
def test_explicit_native_cli_retains_catalog_but_blocks_missing_protected_sources():
    assert os.geteuid()==0, 'Run in the job-owned root verification container'
    input_root=Path('/workspace/input')
    assert input_root.is_dir() and os.access(input_root,os.W_OK), 'Mount a dedicated job-owned input volume'
    os.chown(input_root,10001,10001);input_root.chmod(0o700)
    root=Path(tempfile.mkdtemp(prefix='ai4r-native-init-'))
    try:
        root.chmod(0o755)
        state=root/'state';store=SQLiteRunStore(state,input_root=input_root)
        policy=json.loads(Path('tests/fixtures/research/planning/plan_policy.json').read_bytes())
        policy_ref=store.put_record('plan-policy',policy)
        raw=Path('/opt/ai4r/jiuwenswarm/research_assets/planner/static-template.json').read_bytes()
        static_ref=store.put_blob(raw,media_type='application/json')
        configuration=valid_config();configuration['cc']['plan_policy_ref']=policy_ref
        configuration['cc']['static_template_ref']=static_ref
        configuration_ref=store.append_record('controlled-operator-snapshot',configuration)
        # No hidden dataset, credential, model answer, policy default or
        # execution capability is supplied by this installation-only fixture.
        unavailable=store.put_blob(b'Visible initialization-only binding; no model runtime')
        bindings=store.append_record('controlled-bootstrap-binding',{
            'workspace_id':'fixture:workspace','host_id':'fixture:host',
            'configuration_ref':configuration_ref,'model_selection_profile_ref':unavailable,
            'deployment_ref':unavailable,'protected_options':{}})
        store.close()
        locator=root/'bindings.json';locator.write_text(json.dumps({'binding_ref':bindings}));locator.chmod(0o644)
        operator=root/'config.yaml';operator.write_text(yaml.safe_dump(configuration));operator.chmod(0o644)
        for directory,_,files in os.walk(state):
            os.chown(directory,10001,10001)
            for name in files:os.chown(Path(directory)/name,10001,10001)
        accounts=root/'accounts';accounts.mkdir(mode=0o700);os.chown(accounts,10001,10001)
        environment={**os.environ,'JIUWENSWARM_M1_PROFILE':'1','JIUWENSWARM_M1_STATE':str(state),
            'JIUWENSWARM_M1_ACCOUNTS':str(accounts),'JIUWENSWARM_M1_CONFIG':str(operator),
            'JIUWENSWARM_M1_BOOTSTRAP_BINDINGS':str(locator),
            'JIUWENSWARM_DATA_DIR':str(root/'native'),'JIUWENSWARM_HOME':str(root/'native-home')}
        command=[shutil.which('jiuwenswarm-init'),'--json']
        original_policy=hashlib.sha256(operator.read_bytes()).hexdigest()
        process=subprocess.run(command,env=environment,user=10001,group=10001,extra_groups=(),
            capture_output=True,text=True,timeout=60,cwd='/workspace')
        assert process.returncode==2, process.stderr
        receipt=json.loads(process.stdout)
        assert receipt['status']=='blocked' and receipt['runtime_ready'] is False
        assert receipt['actor']['os_uid']==10001 and receipt['actor']['operator_id'].startswith('os:10001:')
        assert len(receipt['admission_refs'])==1
        assert receipt['static_template_ref'] is None and receipt['library_snapshot_ref'] is None
        assert any(item['code']=='bootstrap_blocked' for item in receipt['diagnostics'])
        assert hashlib.sha256(operator.read_bytes()).hexdigest()==original_policy
        store=SQLiteRunStore(state,input_root=input_root)
        try:
            captured=store.read_record(receipt['receipt_ref'])
            assert captured['binding_ref']==bindings and captured['configuration_ref']==configuration_ref
            assert not list(store.iter_records(kinds=('model-call','candidate-package','activation-record')))
            assert store.connection.execute('SELECT COUNT(*) FROM library_versions').fetchone()[0]==0
            assert all(store.read_record(ref)['status']=='blocked' for ref in receipt['admission_refs'])
            catalog=json.loads(Path('/opt/ai4r/jiuwenswarm/research_assets/catalog.json').read_bytes())
            science=json.loads(Path('/opt/ai4r/jiuwenswarm/research/resources/capsules/capsule_catalog.json').read_bytes())
            for stage in catalog['capsules'].values():
                digest=stage['declaration_sha256'];assert store.read_blob({'id':'blob:'+digest,'sha256':digest})
            for stage in science['stages'].values():assert store.read_blob(stage['declaration_ref'])
            before=[row['ref'] for row in store.iter_records(kinds=('library-admission','activation-record'))]
        finally:store.close()
        repeated=subprocess.run(command,env=environment,user=10001,group=10001,extra_groups=(),
            capture_output=True,text=True,timeout=60,cwd='/workspace')
        assert repeated.returncode==2, repeated.stderr
        assert len(json.loads(repeated.stdout)['admission_refs'])==1
        store=SQLiteRunStore(state,input_root=input_root)
        try:
            after=list(store.iter_records(kinds=('library-admission',)))
            assert len(after)==len(before)+1 and all(row['record']['status']=='blocked' for row in after)
            assert not list(store.iter_records(kinds=('activation-record',)))
            assert store.connection.execute('SELECT COUNT(*) FROM library_versions').fetchone()[0]==0
        finally:store.close()
    finally:
        # Only this explicitly created disposable fixture tree is removed.
        shutil.rmtree(root)
