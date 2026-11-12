"""Factory tests never use the campaign queue or real Docker/GPU tools."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from jiuwenswarm.factory.jobs import Jobs, TERMINAL
from jiuwenswarm.factory.store import Store

JOBQ = Path('/home/muk/projects/siminfeng/bin/jobq')


@pytest.fixture(autouse=True)
def isolated_jobq(tmp_path, monkeypatch):
    directory = tmp_path / 'jobq'
    monkeypatch.setenv('JOBQ_DIR', str(directory))
    assert Path(os.environ['JOBQ_DIR']).is_relative_to(tmp_path)
    assert not Path(os.environ['JOBQ_DIR']).is_relative_to(Path('/home/muk/projects/siminfeng/lab/jobq'))
    fake = tmp_path / 'run_op'
    fake.write_text('#!' + sys.executable + '\nimport subprocess,sys\np=subprocess.Popen(sys.argv[sys.argv.index("--")+1:],start_new_session=True)\nsys.exit(p.wait())\n')
    fake.chmod(0o755)
    monkeypatch.setenv('JOBQ_RUN_OP', str(fake))
    yield directory
    # Kill only groups whose ownership is in this test's private job records.
    for path in directory.glob('job-*.json'):
        job = json.loads(path.read_text())
        for key in ('pgid', 'wrapper_pgid', 'runner_pid'):
            if job.get(key):
                try:
                    os.killpg(job[key], signal.SIGKILL)
                except ProcessLookupError:
                    pass


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / 'factory') as result:
        result.create_task(dict(task_id='t', objective='offline build'))
        yield result


@pytest.fixture
def jobs(store):
    return Jobs(store)


@pytest.fixture
def worker(isolated_jobq):
    processes = []
    def start():
        process = subprocess.Popen([sys.executable, str(JOBQ), 'worker'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        processes.append(process)
        return process
    yield start
    for process in processes:
        process.terminate()
        process.communicate(timeout=5)


def until(jobs, attempt_id, predicate=None, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = jobs.status(attempt_id)
        if (predicate(result) if predicate else result['state'] in TERMINAL):
            return result
        time.sleep(.03)
    pytest.fail('Attempt did not reach expected state: ' + str(result))


@pytest.fixture(autouse=True)
def builder_disk(request, tmp_path, monkeypatch):
    if request.path.name != 'test_builder.py':
        return
    import shutil
    usage = shutil._ntuple_diskusage(32 * 1024**3, 0, 32 * 1024**3)
    monkeypatch.setattr(shutil, 'disk_usage', lambda path: usage)
    # The durable worker is a fresh Python process; install the same fixture there.
    site = tmp_path / 'python-fixture'
    site.mkdir()
    (site / 'sitecustomize.py').write_text(
        'import shutil\nshutil.disk_usage = lambda path: shutil._ntuple_diskusage(34359738368, 0, 34359738368)\n')
    monkeypatch.setenv('PYTHONPATH', str(site) + os.pathsep + str(Path.cwd()))
