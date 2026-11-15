"""Host lifecycle checks use private files and fake Docker, never the lab GPU."""
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from jiuwenswarm.factory import lab_lifecycle as lifecycle


def intent(root):
    root.mkdir()
    value = dict(output=str(root.resolve()), container_name='factory-lab-'+'a'*32,
                 nonce='b'*32, image='sha256:'+'c'*64, owner=lifecycle.process_identity(),
                 deadline_monotonic=time.monotonic()+30)
    lifecycle.atomic_json(root/'intent.json', value)
    return value


def test_process_identity_rejects_stale_start_and_boot():
    current = lifecycle.process_identity()
    assert lifecycle.process_matches(current)
    assert not lifecycle.process_matches(dict(current, start_ticks=current['start_ticks']+1))
    assert not lifecycle.process_matches(dict(current, boot_id='different'))
    assert not lifecycle.process_matches(None)


def test_quiet_lease_blocks_build_and_cpu_then_releases(tmp_path):
    code = '''import sys
from jiuwenswarm.factory.lab_lifecycle import QuietLease
try:
 with QuietLease(sys.argv[1],sys.argv[2],timeout_s=.1): pass
except TimeoutError: sys.exit(42)
'''
    with lifecycle.QuietLease(tmp_path, 'lab', timeout_s=0):
        for kind in ('build', 'cpu', 'lab'):
            result = subprocess.run([sys.executable, '-c', code, str(tmp_path), kind])
            assert result.returncode == 42
    assert subprocess.run([sys.executable, '-c', code, str(tmp_path), 'build']).returncode == 0


def test_shared_build_leases_coexist(tmp_path):
    with lifecycle.QuietLease(tmp_path, 'build', timeout_s=0):
        with lifecycle.QuietLease(tmp_path, 'cpu', timeout_s=0):
            with pytest.raises(TimeoutError):
                with lifecycle.QuietLease(tmp_path, 'lab', timeout_s=0): pass


def fake_docker(monkeypatch, value, *, present=True):
    calls = []
    def call(*args, required=True):
        nonlocal present
        calls.append(args)
        if args[0] == 'rm':
            present = False
            return subprocess.CompletedProcess(args, 0, '', '')
        return subprocess.CompletedProcess(args, 0 if present else 1,
                                           json.dumps([value]) if present else '',
                                           '' if present else 'Error: No such object')
    monkeypatch.setattr(lifecycle, 'docker', call)
    return calls


def owned_info(value):
    return dict(Id='d'*64, Name='/'+value['container_name'], Image=value['image'],
                Config={'Labels': {'factory.lab.owner': 'spark-lab-v1', 'factory.lab.nonce': value['nonce']}},
                State={'Running': True, 'ExitCode': 0, 'OOMKilled': False})


def test_recovery_without_cid_receipt_is_exact_and_replay_safe(tmp_path, monkeypatch):
    root = tmp_path/'run'; value = intent(root)
    info = owned_info(value); calls = fake_docker(monkeypatch, info)
    (root/'stdout.log').write_text('partial tokens\n')
    first = lifecycle.recover_run(root)
    assert first['removed'] and first['was_running']
    saved = (root/'recovery.json').read_bytes()
    sealed = (root/'manifest.json').read_bytes()
    assert lifecycle.recover_run(root)['removed']
    assert (root/'recovery.json').read_bytes() == saved
    assert (root/'manifest.json').read_bytes() == sealed
    assert [c for c in calls if c[0] == 'rm'] == [('rm', '-f', info['Id'])]
    assert json.loads((root/'manifest.json').read_text())['state'] == 'partial'
    assert json.loads((root/'report.json').read_text())['evidence_completeness'] == 'partial'


@pytest.mark.parametrize('wrong', ['nonce', 'image', 'name', 'cid'])
def test_recovery_refuses_identity_mismatch(tmp_path, monkeypatch, wrong):
    root = tmp_path/'run'; value = intent(root); info = owned_info(value)
    if wrong == 'nonce': info['Config']['Labels']['factory.lab.nonce'] = 'wrong'
    if wrong == 'image': info['Image'] = 'sha256:'+'0'*64
    if wrong == 'name': info['Name'] = '/unrelated'
    if wrong == 'cid': lifecycle.atomic_json(root/'container.json', {'container_id': '0'*64})
    calls = fake_docker(monkeypatch, info)
    with pytest.raises(ValueError): lifecycle.recover_run(root)
    assert not any(c[0] == 'rm' for c in calls)


def test_docker_unavailable_is_not_cleanup(tmp_path, monkeypatch):
    root = tmp_path/'run'; intent(root)
    monkeypatch.setattr(lifecycle, 'docker', lambda *a, **kw: subprocess.CompletedProcess(a, 1, '', 'Cannot connect to Docker daemon'))
    with pytest.raises(RuntimeError, match='Cannot establish'): lifecycle.recover_run(root)
    assert not (root/'report.json').exists()


def test_intent_path_escape_rejected(tmp_path):
    root = tmp_path/'run'; value = intent(root)
    lifecycle.atomic_json(root/'intent.json', dict(value, output='/different'))
    with pytest.raises(ValueError): lifecycle.load_intent(root)


def test_lowercase_missing_object_is_accepted(tmp_path, monkeypatch):
    root = tmp_path/'run'; value = intent(root)
    monkeypatch.setattr(lifecycle, 'docker', lambda *a, **kw: subprocess.CompletedProcess(a, 1, '', 'error: no such object: '+value['container_name']))
    assert lifecycle.recover_run(root)['removed']


def test_inherited_guardian_descriptor_retains_quiet_lease(tmp_path):
    child = None
    try:
        with lifecycle.QuietLease(tmp_path, 'lab', timeout_s=0) as lease:
            child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(10)'], pass_fds=(lease.fd,))
        # Owner closed its descriptor; a guardian holding the inherited open
        # file description still fences builds until recovery finishes.
        with pytest.raises(TimeoutError):
            with lifecycle.QuietLease(tmp_path, 'build', timeout_s=.1): pass
        child.terminate(); child.wait(timeout=3)
        with lifecycle.QuietLease(tmp_path, 'build', timeout_s=.1): pass
    finally:
        if child and child.poll() is None: child.kill(); child.wait(timeout=3)


def test_native_build_guard_exposes_owner_and_holds_shared_lease(tmp_path, monkeypatch):
    calls=[]
    class Process:
        pid=__import__('os').getpid()
        def wait(self,timeout):return 0
    monkeypatch.setattr(lifecycle.subprocess,'Popen',lambda *a,**kw: (calls.append((a,kw)) or Process()))
    monkeypatch.setattr(lifecycle,'recover_run',lambda *a,**kw: dict(removed=True))
    root=tmp_path/'native-owner';leases=tmp_path/'leases'
    with lifecycle.OwnedContainerGuard(root,'sha256:'+'f'*64,lease_root=leases,timeout_s=30) as guard:
        assert guard.name.startswith('factory-lab-')
        assert guard.labels['factory.lab.role']=='build'
        assert guard.labels['factory.lab.nonce']==json.loads((root/'intent.json').read_text())['nonce']
        with pytest.raises(TimeoutError):
            with lifecycle.QuietLease(leases,'lab',timeout_s=0):pass
        assert calls[0][1]['start_new_session'] is True
        assert len(calls[0][1]['pass_fds'])==1
    assert json.loads((root/'report.json').read_text())['container_removed'] is True
    with lifecycle.QuietLease(leases,'lab',timeout_s=0):pass
