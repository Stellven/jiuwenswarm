"""Fast-lab control flow with a fake scope, Docker responses and SSE stream."""
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.factory import capped_run
from scripts.factory import lab_v4_fast


@pytest.fixture
def lab(tmp_path, monkeypatch):
    events = []
    image_id = 'sha256:' + 'a' * 64
    binary = b'llama-server fixture'
    digest = hashlib.sha256(binary).hexdigest()
    arm = dict(image='fixture:engine', expect_sha256=digest, model=str(tmp_path / 'pack.gguf'), cache_mib=64)
    prompts = {}
    for size in ('p512', 'p2048'):
        path = tmp_path / f'{size}.txt'
        path.write_text(size)
        prompts[size] = str(path)
    out = tmp_path / 'out'
    config = dict(out_dir=str(out), device_budget_mib=110000, prompts=prompts,
                  arms=dict(B=arm, P={**arm, 'args': ['-b', '2048', '-ub', '2048']}))
    config_path = tmp_path / 'config.json'
    config_path.write_text(json.dumps(config))

    def docker(args, **kwargs):
        assert args[0] == 'docker'
        events.append(('docker', *args[1:3]))
        if args[1] == 'image':
            return SimpleNamespace(stdout=image_id)
        if args[1] == 'create':
            assert args[2] == image_id
            return SimpleNamespace(stdout='stopped-container')
        if args[1] == 'cp':
            directory = Path(args[-1])
            directory.mkdir()
            (directory / 'llama-server').write_bytes(binary)
        return SimpleNamespace(stdout='')

    def machine(task, home):
        assert home == out
        events.append(('gate',))
        foreign = ['729, fixture, 8 MiB'] if events.count(('gate',)) == 1 else []
        return dict(ok=not foreign, available_gib=116, need_available_gib=100, foreign_gpu_processes=foreign)

    def popen(argv, **kwargs):
        events.append(('launch', argv))
        kwargs['stderr'].write(b'llama_context: n_batch = 2048, n_ubatch = 2048\n')
        proc = SimpleNamespace(pid=-1, returncode=None)
        proc.poll = lambda: proc.returncode
        return proc

    def stop(proc):
        events.append(('stop',))
        proc.returncode = 0

    def urlopen(req, **kwargs):
        if isinstance(req, str):
            assert req.endswith('/health')
            return Health()
        data = json.loads(req.data)
        events.append(('request', data))
        timings = dict(prompt_n=511 if data['prompt'] == 'p512' else 2047, prompt_ms=500,
                       prompt_per_second=125, predicted_n=32, predicted_per_second=1.5)
        return io.BytesIO(b'data: {"content":"Sample","stop":false}\n\n'
                          + f'data: {json.dumps(dict(stop=True, timings=timings))}\n'.encode())

    class Health(io.BytesIO):
        status = 200

    monkeypatch.setattr(lab_v4_fast.subprocess, 'run', docker)
    monkeypatch.setattr(capped_run, 'machine', machine)
    monkeypatch.setattr(capped_run, '_free_port', lambda: 8097)
    monkeypatch.setattr(capped_run, '_meminfo', lambda: dict(MemAvailable=120000 << 20, MemTotal=124608 << 20))
    monkeypatch.setattr(capped_run, 'stop', stop)
    monkeypatch.setattr(capped_run.subprocess, 'Popen', popen)
    monkeypatch.setattr(capped_run.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(capped_run.urllib.request, 'urlopen', urlopen)
    monkeypatch.setattr(lab_v4_fast, 'evict', lambda model: events.append(('evict',)))
    return SimpleNamespace(events=events, config=config, path=config_path, out=out, image_id=image_id, digest=digest)


def test_delivery_image_uses_the_capped_runner_for_each_arm(lab):
    lab_v4_fast.main(lab.path, ['B', 'P'])
    events = lab.events
    assert [event[0] for event in events if event[0] != 'docker'] == [
        'gate', 'gate', 'evict', 'launch', 'evict', 'request', 'request', 'evict', 'request', 'request', 'stop',
        'gate', 'evict', 'launch', 'evict', 'request', 'request', 'evict', 'request', 'request', 'stop',
    ]
    assert sum(event[:2] == ('docker', 'create') for event in events) == 1
    for _, argv in (event for event in events if event[0] == 'launch'):
        assert argv[:7] == ['systemd-run', '--user', '--scope', '--quiet', '-p', 'MemoryMax=96G', '-p']
        assert 'MemorySwapMax=0' in argv
        assert argv[argv.index('-fitt') + 1] == '10000'
        assert argv[argv.index('-fit') + 1] == 'on'
    for _, body in (event for event in events if event[0] == 'request'):
        assert body == dict(prompt=body['prompt'], n_predict=32, temperature=0, seed=1, cache_prompt=False, stream=True)
    report = json.loads((lab.out / 'report.json').read_text())
    assert [(row['arm'], row['request'], row['state']) for row in report['rows']] == [
        (arm, prompt, state) for arm in ('B', 'P') for prompt in ('p512', 'p2048') for state in ('cold', 'warm')
    ]
    assert report['images']['B'] == dict(image='fixture:engine', image_id=lab.image_id, llama_server_sha256=lab.digest)
    assert report['arms']['P']['device_budget_mib'] == 110000
    assert report['arms']['P']['argv'][report['arms']['P']['argv'].index('-ub') + 1] == '2048'
    assert report['rows'][0]['decode_tokens_per_second'] == 1.5
    previous = events[:]
    lab_v4_fast.main(lab.path, ['B', 'P'])
    assert events == previous


def test_digest_mismatch_in_either_arm_blocks_all_loads(lab):
    lab.config['arms']['P']['expect_sha256'] = 'b' * 64
    lab.path.write_text(json.dumps(lab.config))
    with pytest.raises(SystemExit, match='P: llama-server.*expected'):
        lab_v4_fast.main(lab.path, ['B', 'P'])
    assert all(event[0] == 'docker' for event in lab.events)


def test_loading_memory_floor_stops_the_arm(lab, monkeypatch):
    monkeypatch.setattr(capped_run, '_meminfo', lambda: dict(MemAvailable=7 << 30, MemTotal=124608 << 20))
    with pytest.raises(capped_run.RunError, match='available memory fell to 7.0 GiB'):
        lab_v4_fast.main(lab.path, ['B', 'P'])
    assert [event[0] for event in lab.events if event[0] != 'docker'] == [
        'gate', 'gate', 'evict', 'launch', 'stop',
    ]


def test_binary_directory_and_skip_warm_still_work(lab):
    arm = lab.config['arms']['B']
    arm.pop('image')
    arm.pop('expect_sha256')
    arm['bin'] = str(lab.path.parent)
    arm['skip_warm'] = ['p512']
    (lab.path.parent / 'llama-server').write_bytes(b'local fixture')
    lab.path.write_text(json.dumps(lab.config))

    lab_v4_fast.main(lab.path, ['B'])

    assert not any(event[0] == 'docker' for event in lab.events)
    report = json.loads((lab.out / 'report.json').read_text())
    assert [(row['request'], row['state']) for row in report['rows']] == [
        ('p512', 'cold'), ('p2048', 'cold'), ('p2048', 'warm'),
    ]
