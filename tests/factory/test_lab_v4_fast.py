"""Fast-lab control flow with a fake scope, Docker responses and SSE stream."""
import hashlib
import io
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

from jiuwenswarm.factory import capped_run, node_check
from jiuwenswarm.factory.store import Store
from scripts.factory import lab_v4_fast, lab_v4_inputs, lab_v4_quiet


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
        ubatch = argv[argv.index('-ub') + 1] if '-ub' in argv else '512'
        kwargs['stderr'].write(f'llama_context: n_batch = 2048\nllama_context: n_ubatch = {ubatch}\n'
                               'impl: CUDA0 MoE cache size = 63.00 MiB\n'.encode())
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


@pytest.fixture(params=['inline', 'artifact'])
def factory(lab, tmp_path, request, monkeypatch):
    monkeypatch.setattr(lab_v4_quiet.os, 'getloadavg', lambda: (0.1, 0.2, 0.3))
    monkeypatch.setattr(lab_v4_quiet, 'processes', lambda: dict(process_count=1, processes=[
        dict(pid=101, ppid=1, state='R', kind='helper', own_lab=True)]))
    home = tmp_path / 'factory'
    store = Store(home)
    task = lab_v4_inputs.TASK
    store.create_task(dict(task_id=task, objective='Synthetic completed lab delivery'))

    def document(key, data):
        return store.put_artifact(task, key, json.dumps(data).encode(), 'application/json', None)

    def attempt(kind, request):
        key = uuid4().hex
        store.create_attempt(task, dict(attempt_id=key, kind=kind, idem_key=key, fingerprint=key, request=request))
        store.transition_attempt(task, key, 'running')
        store.transition_attempt(task, key, 'succeeded')
        return key

    commit = 'c' * 40
    build = attempt('build', dict(node_id='build_image', verify_image=True, source=dict(commit=commit)))
    check = document(build + ':image-check', dict(format='factory.image-check/1', status='passed',
                     image_id=lab.image_id, source_commit=commit, executable_sha256=lab.digest))
    document(build + ':receipt', dict(image_id=lab.image_id, executable_sha256=lab.digest,
                                      image_check={key: check[key] for key in ('artifact_id', 'sha256')}))

    model = tmp_path / 'pack.gguf'
    model.write_bytes(b'GGUF fixture')
    model_sha = hashlib.sha256(model.read_bytes()).hexdigest()
    manifest = model.with_suffix('.manifest.json')
    manifest.write_text(json.dumps(dict(format='factory.pack-manifest/1', bytes=model.stat().st_size,
                                        files=[dict(name=model.name, bytes=model.stat().st_size, sha256=model_sha)])))
    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    quant = attempt('pack_replay', dict(node_id='requant_2bit'))
    manifest_id = f'run-{quant[:12]}-pack-manifest.json'
    store.put_artifact(task, manifest_id, manifest, 'application/json', None)
    store.append_observation(task, dict(obs_id='replay', kind='capped_run', source_artifacts=[manifest_id],
        values=dict(node_id='requant_2bit', recipe='quantize', outcome='ok', replayed_from=dict(job_id='historical'),
                    attempt_id=quant, result=dict(first_shard=str(model), manifest=str(manifest), manifest_sha256=manifest_sha))))

    plan = dict(format='factory.prefill-batch-plan/1', batch=2048, ubatch=2048, moe_cache_mib=64, fits=True,
                prompt_tokens=[511, 2047], args=['-b', '2048', '-ub', '2048', '--moe-cache-mib', '64'],
                device_budget_mib=110000, reference=dict(n_batch=2048, n_ubatch=512))
    call = str(uuid4())
    call_path = home / 'ccstore' / 'attempts' / call / 'receipt.json'
    call_path.parent.mkdir(parents=True)
    verifier = dict(cc='engine.size_prefill_batch', capability='verify', release='release')
    plan_input = json.dumps(plan, indent=1)
    refs = {'evidence_ids': []}
    if request.param == 'artifact':
        sealed_plan = document('verified-plan', plan)
        plan_input = str(home / sealed_plan['location'])
        refs['evidence_ids'].append(sealed_plan['artifact_id'])
    inputs = dict(plan=plan_input, device_budget_mib=110000)
    entry, subject = {'name': 'batch_plan'}, 'subject-digest'
    key = node_check._sha(dict(task=task, node='size_prefill_batch', entry=entry, records=subject,
                               verifier=verifier, inputs=inputs, reviewer=None))
    request_path = home / 'node-checks' / key[:32] / 'request.json'
    request_path.parent.mkdir(parents=True)
    request_path.write_text(json.dumps(dict(reviewer=None, refs=refs)))
    call_path.write_text(json.dumps(dict(call=call, release='release', capability='verify', key='node-check-' + key,
        state='succeeded', outputs=dict(done=True), provenance=dict(inputs=inputs))))
    document('lab-package:delivery', dict(origin=dict(task_id=task, node_id='deliver_to_lab'), subjects={
        'image': dict(kind='container_image', build_attempt_id=build, identity=dict(id=lab.image_id)),
        'pack': dict(kind='model_pack', payload=dict(artifact_id=manifest_id, sha256=manifest_sha)),
    }))
    checks = [
        ('build_image', 'image', dict(found=dict(build_attempt_id=build, image_id=lab.image_id))),
        ('size_prefill_batch', 'batch_plan', dict(key=key, entry=entry, diff_sha256=subject, refs=refs,
            verifier=dict(verifier, call=call, passed=True))),
        ('deliver_to_lab', 'lab_request', dict(found=dict(package_id='delivery', request_id='sent'))),
    ]
    nodes = [dict(node_id='requant_2bit', title='Quantize', kind='inspect', state='done', evidence_ids=['replay'])]
    for node, output, fields in checks:
        check_id = f'check:{node}'
        store.append_observation(task, dict(obs_id=check_id, kind='node_check',
            values=dict(node_id=node, output=output, state='finished', passed=True, **fields)))
        nodes.append(dict(node_id=node, kind='inspect', title=node, state='done', evidence_ids=[check_id]))
    store.append_observation(task, dict(kind='taskgraph_patch', values=dict(rev=1, parent_rev=0, decision_rev=0,
                                                                             patch=dict(add=nodes))))
    reference_path = tmp_path / 'baseline.json'
    reference_path.write_text(json.dumps(dict(rows=[dict(arm='A', request=size, state=state, prompt_tokens=tokens,
        generated_tokens=128, client_ttft_ms=10000, decode_tokens_per_second=0.4, request_total_ms=330000)
        for size, tokens in lab_v4_inputs.PROMPT_TOKENS.items() for state in ('cold', 'warm')])))
    lab.config.pop('arms')
    lab.config.pop('device_budget_mib')
    lab.config.update(factory_run=dict(home=str(home), task_id=task), baseline_report=str(reference_path))
    lab.path.write_text(json.dumps(lab.config))
    return SimpleNamespace(home=home, plan=plan, manifest=manifest, manifest_sha=manifest_sha,
                           call_path=call_path, reference=reference_path)


def test_factory_rows_use_delivered_identity_and_server_settings(lab, factory):
    lab_v4_fast.main(lab.path, ['B', 'P'])
    report = json.loads((lab.out / 'report.json').read_text())
    assert report['batch_plan'] == factory.plan
    assert len(report['rows']) == 8
    for row in report['rows']:
        assert row['image_id'] == lab.image_id
        assert row['llama_server_sha256'] == lab.digest
        assert row['pack_manifest_sha256'] == factory.manifest_sha
        assert row['n_batch'] == 2048
        assert row['n_ubatch'] == (512 if row['arm'] == 'B' else 2048)
        assert row['batch_mode'] == ('default' if row['arm'] == 'B' else 'planned')
        assert row['requested_moe_cache_mib'] == 64
        assert row['moe_cache_mib'] == 63.0
        assert row['batch_plan'] == dict(batch=2048, ubatch=2048, moe_cache_mib=64)
        assert row['cache_prompt'] is False
        assert row['quiet']['status'] == 'accepted'
        assert [sample['phase'] for sample in row['quiet']['samples']] == ['start', 'end']
        assert row['quiet']['samples'][0]['load_averages'] == [0.1, 0.2, 0.3]
    computed = lab_v4_fast.comparison(report['rows'], lab_v4_fast.baseline(factory.reference))
    assert report['comparison'] == computed
    assert len(computed['cells']) == 8
    for cell in computed['cells']:
        assert cell['baseline_a']['image_id'] is None
        assert cell['baseline_a']['pack_manifest_sha256'] is None
        assert cell['baseline_a']['generated_tokens'] == [128]
        assert cell['measured']['generated_tokens'] == [32]
        assert cell['same_prompt_tokens'] and not cell['same_generated_tokens']
        assert 'request_total_ms' not in cell['delta_vs_a']

    Path(lab.config['prompts']['p512']).write_text('changed')
    with pytest.raises(ValueError, match='inputs differ'):
        lab_v4_fast.main(lab.path, ['B'])
    assert sum(event[0] == 'launch' for event in lab.events) == 2


def test_changed_pack_manifest_prevents_any_load(lab, factory):
    factory.manifest.write_text(factory.manifest.read_text() + '\n')
    with pytest.raises(ValueError, match='Pack manifest changed'):
        lab_v4_fast.main(lab.path, ['B'])
    assert not lab.events


def test_factory_plan_must_be_the_accepted_verifier_input(lab, factory):
    receipt = json.loads(factory.call_path.read_text())
    receipt['provenance']['inputs']['plan'] = '{}'
    factory.call_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='verifier inputs differ'):
        lab_v4_fast.main(lab.path, ['P'])
    assert not lab.events


def test_quiet_preflight_prevents_image_extraction_and_model_load(lab, factory, monkeypatch):
    monkeypatch.setattr(lab_v4_quiet.os, 'getloadavg', lambda: (1.0, 0.1, 0.1))
    with pytest.raises(lab_v4_quiet.Breach, match='one-minute load at or above limit'):
        lab_v4_fast.main(lab.path, ['B', 'P'])
    report = json.loads((lab.out / 'report.json').read_text())
    assert report['quiet_admissions'][0]['load_averages'] == [1.0, 0.1, 0.1]
    assert report['rows'] == []
    assert not lab.events


def test_quiet_rechecked_after_machine_gate_and_after_loading(lab, factory, monkeypatch):
    original = lab_v4_quiet.snapshot
    waited = set()
    monkeypatch.setattr(lab_v4_quiet, 'WAIT_SECONDS', 0.001)

    def sample(limits, phase):
        result = original(limits, phase)
        if phase not in waited:
            if phase == 'pre_launch_wait':
                result.update(ok=False, reasons=['foreign build process present'])
                result['process_count'] += 1
                result['processes'].append(dict(pid=102, ppid=1, state='R', kind='build', own_lab=False))
            elif phase in {'ready', 'start_wait'}:
                result['load_averages'][0] = 1.2
                result.update(ok=False, reasons=['one-minute load at or above limit'])
        waited.add(phase)
        return result

    monkeypatch.setattr(lab_v4_quiet, 'snapshot', sample)
    lab_v4_fast.main(lab.path, ['B'])
    report = json.loads((lab.out / 'report.json').read_text())
    assert len(report['rows']) == 4 and all(row['quiet']['status'] == 'accepted' for row in report['rows'])
    outside = report['quiet_arms'][0]['samples']
    assert {sample['phase'] for sample in outside if not sample['ok']} >= {'pre_launch_wait', 'ready', 'start_wait'}
    assert sum(event[0] == 'launch' for event in lab.events) == 1
    assert sum(event[0] == 'gate' for event in lab.events) == 3


def test_mid_request_violation_excludes_only_its_cell_and_keeps_warm_predecessor(lab, factory, monkeypatch):
    real_sample = lab_v4_quiet.snapshot
    real_request = lab_v4_fast.request
    sampled_during, waited_before_warm = Event(), Event()
    monkeypatch.setattr(lab_v4_quiet, 'INTERVAL_SECONDS', 0.05)
    monkeypatch.setattr(lab_v4_quiet, 'WAIT_SECONDS', 0.001)

    def sample(limits, phase):
        result = real_sample(limits, phase)
        if phase == 'during' and not sampled_during.is_set():
            result['ok'] = False
            result['reasons'] = ['foreign test process present']
            result['process_count'] += 1
            result['processes'].append(dict(pid=102, ppid=1, state='R', kind='test', own_lab=False))
            sampled_during.set()
        elif phase == 'start_wait' and sampled_during.is_set() and not waited_before_warm.is_set():
            result['load_averages'][0] = 1.1
            result.update(ok=False, reasons=['one-minute load at or above limit'])
            waited_before_warm.set()
        return result

    def capture_then_finish(*args):
        metrics = real_request(*args)
        assert sampled_during.wait(5)
        return metrics

    monkeypatch.setattr(lab_v4_quiet, 'snapshot', sample)
    monkeypatch.setattr(lab_v4_fast, 'request', capture_then_finish)
    with pytest.raises(capped_run.RunError, match='excluded timed cells'):
        lab_v4_fast.main(lab.path, ['B', 'P'])
    report = json.loads((lab.out / 'report.json').read_text())
    assert len(report['rows']) == 8
    row, warm = report['rows'][:2]
    assert (row['arm'], row['state'], row['request']) == ('B', 'cold', 'p512')
    assert row['decode_tokens_per_second'] == 1.5
    phases = [sample['phase'] for sample in row['quiet']['samples']]
    assert phases[0] == 'start' and phases[-1] == 'end' and 'during' in phases
    assert row['quiet']['status'] == 'excluded'
    assert (warm['arm'], warm['state'], warm['request']) == ('B', 'warm', 'p512')
    assert warm['quiet']['status'] == 'accepted' and waited_before_warm.is_set()
    assert len(report['summary']) == len(report['comparison']['cells']) == 7
    assert report['comparison']['excluded'] == [dict(arm='B', request='p512', state='cold',
                                                     reasons=['foreign test process present'])]
    assert sum(event[0] == 'request' for event in lab.events) == 8
    assert sum(event[0] == 'launch' for event in lab.events) == 2

    previous = lab.events[:]
    with pytest.raises(capped_run.RunError, match='excluded timed cells'):
        lab_v4_fast.main(lab.path, ['B', 'P'])
    assert lab.events == previous


def test_resume_does_not_replay_a_cold_cell_to_create_a_warm_predecessor(lab, factory):
    lab_v4_fast.main(lab.path, ['B'])
    report_path = lab.out / 'report.json'
    report = json.loads(report_path.read_text())
    cold = report['rows'][0]
    report['rows'] = [cold]
    report_path.write_text(json.dumps(report))
    lab.events.clear()

    with pytest.raises(capped_run.RunError, match='excluded timed cells'):
        lab_v4_fast.main(lab.path, ['B'])
    updated = json.loads(report_path.read_text())
    assert updated['rows'][0] == cold
    assert len(updated['rows']) == 4
    assert [event[1]['prompt'] for event in lab.events if event[0] == 'request'] == ['p2048', 'p2048']
    assert updated['comparison']['excluded'] == [dict(arm='B', request='p512', state='warm', reasons=[
        'warm state unavailable after restart; cold predecessor ran on another load'])]


def test_offline_comparison_excludes_partial_factory_evidence(lab, factory):
    lab_v4_fast.main(lab.path, ['B'])
    report = json.loads((lab.out / 'report.json').read_text())
    missing, incomplete, accepted, *_ = report['rows']
    missing.pop('quiet')
    incomplete['quiet']['samples'].pop()
    result = lab_v4_fast.comparison([missing, incomplete, accepted], lab_v4_fast.baseline(factory.reference))
    assert len(result['cells']) == 1
    assert result['cells'][0]['request'] == accepted['request']
    assert [item['reasons'] for item in result['excluded']] == [
        ['missing quiet evidence'], ['missing start, periodic or end quiet evidence']]


def test_server_peak_rss_reads_server_high_water_instead_of_launcher(tmp_path):
    launcher = tmp_path / '2'
    (launcher / 'task/2').mkdir(parents=True)
    (launcher / 'comm').write_text('systemd-run')
    (launcher / 'task/2/children').write_text('3')
    child = tmp_path / '3'
    child.mkdir()
    (child / 'comm').write_text('llama-server')
    (child / 'status').write_text('VmHWM:   4096 kB\nVmRSS:   1024 kB\n')
    assert lab_v4_fast.server_peak_rss(2, tmp_path) == 4096 * 1024
    assert lab_v4_fast.server_peak_rss(4, tmp_path) is None
