import pytest
from jiuwenswarm.research_sidecar.cleanup import cleanup_plan
from jiuwenswarm.research_sidecar.launcher import HostLauncher


def test_cleanup_uses_exact_job_resources_only():
    manifest={'job_id':'j','project':'ai4r-qa-j','resources':[{'kind':'container','id':'owned','disposable':True},{'kind':'volume','id':'results','disposable':False}]}
    assert cleanup_plan(manifest,{'owned':{'job_id':'j','project':'ai4r-qa-j'}})==[{'kind':'container','id':'owned'}]
    with pytest.raises(ValueError):cleanup_plan(manifest,{'owned':{'job_id':'other','project':'ai4r-qa-j'}})


def test_host_commands_use_only_finite_overlays_and_separate_referee_authority(tmp_path,monkeypatch):
    import subprocess
    seen=[]
    monkeypatch.setattr('jiuwenswarm.research_sidecar.launcher.docker_prefix',lambda:['docker'])
    def capture(args,**kwargs):
        seen.append((args,kwargs));return subprocess.CompletedProcess(args,0,'','')
    monkeypatch.setattr('jiuwenswarm.research_sidecar.launcher.subprocess.run',capture)
    manifest={'job_id':'owned','project':'ai4r-qa-owned','resources':[],
        'compose_files':['deploy/m1/compose.sidecar.yaml','deploy/m1/compose.rsi.yaml']}
    host=HostLauncher(tmp_path,manifest);host.start();host.run_case(campaign='frozen',case='rsi',variant='baseline',run_id='r001')
    assert all('deploy/m1/compose.sidecar.yaml' in row[0] for row in seen)
    assert 'benchmark' in seen[1][0] and 'sidecar' in seen[1][0] and '--run-id' in seen[1][0]
    assert '--profile' in seen[0][0] and seen[0][0][-1]=='app'
    with pytest.raises(ValueError):HostLauncher(tmp_path,{**manifest,'compose_files':['unapproved.yaml']})
    with pytest.raises(ValueError):host.run_case(campaign='bad/../path',case='rsi',variant='baseline')


def test_host_cleanup_rechecks_actual_labels_before_any_removal(tmp_path,monkeypatch):
    manifest={'job_id':'owned','project':'ai4r-qa-owned','resources':[{'id':'foreign','kind':'container','disposable':True}]}
    host=HostLauncher(tmp_path,manifest)
    monkeypatch.setattr(host,'_observed',lambda _: {'job_id':'other','project':'ai4r-qa-owned'})
    monkeypatch.setattr(host,'_docker',lambda *_args,**_kwargs:(_ for _ in ()).throw(AssertionError('must not stop/remove a foreign resource')))
    with pytest.raises(ValueError):host.cleanup()
