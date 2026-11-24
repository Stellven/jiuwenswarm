"""CPU fixture containers exercise the real worker, retained artifacts and collector."""
import json
from types import SimpleNamespace
import pytest
from tests.factory.test_construction import prepared_loop
from jiuwenswarm.factory import experiment_jobs as worker
from jiuwenswarm.factory.jobs import Jobs


@pytest.mark.parametrize('copy_result',[0,1,'timeout'])
def test_copy_result_controls_retained_evidence_and_downstream(tmp_path,monkeypatch,copy_result):
    store,loop,spec=prepared_loop(tmp_path)
    loop.prepare_experiment('probe',spec,'sha256:'+'a'*64)
    loop.select('probe',['seed'],spec['hypothesis'],expected_rev=0,experiment_id='probe')
    cycle=loop.execute('probe');task=cycle['child_task_id'];aid=cycle['attempt_id']
    root=store.home/'experiment-spool'/aid
    class Guard:
        def __init__(self,output,image,**kwargs):self.output=output;self.name='cpu-fixture';self.labels={}
        def __enter__(self):self.output.mkdir(parents=True);return self
        def __exit__(self,*args):(self.output/'report.json').write_text(json.dumps({'container_removed':True}))
    monkeypatch.setattr(worker,'OwnedContainerGuard',Guard)
    monkeypatch.setattr(worker.subprocess,'check_output',lambda *a,**kw:json.dumps([{'Id':'sha256:'+'a'*64}]))
    def run(argv,**kw):
        if argv[1]=='inspect':return SimpleNamespace(returncode=0,stdout=json.dumps([{'State':{'ExitCode':0}}]))
        assert argv[1]=='cp'
        (root/'artifacts').mkdir();(root/'artifacts/partial.txt').write_text('retained partial payload')
        if copy_result=='timeout':raise worker.subprocess.TimeoutExpired(argv,30,stderr='copy stalled')
        return SimpleNamespace(returncode=copy_result,stdout='',stderr='copy failed' if copy_result else '')
    monkeypatch.setattr(worker.subprocess,'run',run)
    def bounded(*args):
        (root/'stdout').write_text('execution finished');(root/'stderr').write_text('available diagnostics')
        return dict(returncode=0,stop_reason=None,output_bytes=42,elapsed_s=1)
    monkeypatch.setattr(worker,'bounded_run',bounded)
    monkeypatch.setattr(Jobs,'status',lambda self,ident:self._get(ident))
    rc=worker.run(store,task,aid,cycle['contract_path'])
    assert rc==(0 if copy_result==0 else 1)
    # Even a misleading queue success cannot upgrade missing evidence.
    store.transition_attempt(task,aid,'running');store.transition_attempt(task,aid,'succeeded')
    loop.benchmark=worker.ExperimentJobs(store)
    result=loop.benchmark.result(task,aid)
    assert result['analysis']['execution_outcome']=='ok'
    assert result['analysis']['verified_complete']==(copy_result==0)
    assert result['state']==('succeeded' if copy_result==0 else 'failed')
    assert store.artifact_bytes(task,aid+':stdout')==b'execution finished'
    assert store.artifact_bytes(task,aid+':artifacts/partial.txt')==b'retained partial payload'
    # Changing the mutable spool does not change digest-checked retained results.
    (root/'result.json').write_text('{"status":"succeeded"}')
    collected=loop.collect('probe')
    report=store.read(loop.task_id,collected['evidence_id'])['values']
    assert report['verified_complete']==(copy_result==0)
    assert collected['followup']['status']==('evidence_ready' if copy_result==0 else 'incomplete_evidence')
    assert report['promotion_authorized'] is False and report['raw_artifacts']
    if copy_result:
        assert report.get('artifact_copy_stderr')
    store.close()


def test_authored_diagnostic_cannot_authorize_acceptance(tmp_path):
    from jiuwenswarm.factory.acceptance import validate
    store,loop,spec=prepared_loop(tmp_path)
    with pytest.raises(ValueError,match='diagnostic evidence'):validate(store,loop.task_id)
    store.close()
