"""Independent Run 4 scorer tests use no model, device, native graph, or real mailbox."""
import json
from pathlib import Path

import pytest

from jiuwenswarm.factory.ccs.kv_reuse_lab.request_log import first_cached_tasks
from jiuwenswarm.factory.lab_agent import LabAgent
from jiuwenswarm.factory.lab_mailbox import Mailbox, canonical
from jiuwenswarm.factory.muse_r11_scoring import ARMS, CELLS, GIB, NATIVE_COUNTERS, evaluate, sha, token_digest
from scripts.factory.report_muse_r11_lab import stage_report
from scripts.factory import lab_warmup as w2

ROOT = Path(__file__).resolve().parents[2]
REQUEST = 'labreq-' + '1' * 24
PROFILE = 'a' * 64
EXEC = 'b' * 64
IMAGE = 'sha256:' + 'c' * 64
CONTRACT_SHA = 'd' * 64
DELIVERY = {'obs_id': 'native-delivery', 'executable_sha256': EXEC}
PROMPTS = {n: (sha(str(n).encode()), n - 1, sha(f'tokens-{n}'.encode())) for n in (512, 2048)}
DEVICE_MIB = dict(model=18000, moe_cache=62464, kv=14000, compute=8000, host_compute=200)


@pytest.fixture
def package():
    path = ROOT / 'jiuwenswarm/factory/contracts/muse-2bit-demo-r11-amendment-032.json'
    contract = json.loads(path.read_bytes())
    protocol = contract['extensions']['muse.r11-seeding']
    tests = [dict(id=check['id'], check=check['id'], arms=check['applies_to']) for check in contract['correctness']['checks']]
    request = ['client_ttft_ms', 'request_total_ms', 'decode_tokens_per_second', 'cache_hit_rate']
    tests += [dict(id='measure', measure=request, requests=list(CELLS), arms=list(ARMS)),
              dict(id='load', measure=[key for key in contract['measurement']['metrics'] if key not in request],
                   arms=list(ARMS))]
    body = dict(schema='factory.lab-package/1', origin=dict(task_id=contract['contract_id'], node_id='deliver_to_lab'),
        contract=dict(id=contract['contract_id'], sha256=CONTRACT_SHA, document=contract, format=2),
        subjects=dict(image=dict(kind='container_image', identity={'id': IMAGE}, build_attempt_id='image-build',
                                 verification={'verified': True}),
                      seeding_profile=dict(kind='artifact', transfer='attach', payload={'sha256': PROFILE})),
        lab_task=dict(lab_task_id='lab-task', arms={'AQBC': {'subject': 'image'},
                                                  'AQBCE': {'subject': 'image', 'env': protocol['profile_env']}},
                      tests=tests, deliverables=dict(raw_samples=True, sections=['setup', 'results', 'deviations'],
                        files=[{'name': name} for name in ('load-receipts.json', 'warmup-receipts.json',
                                                           'startup-fill-receipts.json', 'request-receipts.json')])))
    return dict(body, package_id='labpkg-' + sha(canonical(body).encode())[:32])


def make_arm(package, arm, *, warm_gain=True, bad_tokens=False, counter_tamper=False):
    seeded = arm == 'AQBCE'
    protocol = package['contract']['document']['extensions']['muse.r11-seeding']
    fixtures = bytearray()
    counters = {key: 0 for key in NATIVE_COUNTERS}
    count = 0
    rows = []

    def place(data):
        start = len(fixtures)
        fixtures.extend(data)
        return dict(path='server.log', start=start, end=len(fixtures))

    def native(marker, value):
        return place((marker + ' ' + json.dumps(value) + '\n').encode())

    def native_task(tokens, cached):
        nonlocal count
        count += 1
        prefix = f'slot id 0 | task {count} | '
        return place(('\n'.join(prefix + line for line in (
            'processing task, child', f'new prompt, task.n_tokens = {tokens}',
            f'cached n_tokens = {cached}, memory_seq_rm [{cached}, end)', 'stop processing: complete',
        )) + '\n').encode())

    inventory = {
        'CUDA0 model buffer size': 'model', 'CUDA0 KV buffer size': 'kv',
        'CUDA0 MoE cache size': 'moe_cache', 'CUDA0 compute buffer size': 'compute',
        'CUDA_Host compute buffer size': 'host_compute',
    }
    place(''.join(f'{message} = {DEVICE_MIB[name]:.2f} MiB\n' for message, name in inventory.items()).encode())
    ready_end = len(fixtures)
    fill = int(seeded)
    group = dict(group=1, slots_admitted=fill, slots_populated=fill,
                 charged_bytes=fill * (53 << 30), uploaded_bytes=fill * (53 << 30))
    startup = {key: value for key, value in group.items() if key != 'group'}
    startup.update(enabled=seeded, seed_ms=fill * 2500, groups=[group] if seeded else [])
    source = native('muse_cache_startup', startup)
    startup.update(format='muse-r11-startup-fill/1', arm=arm, source=source)
    after = native('muse_cache_counters', counters)

    def request(cell, repeat, nominal, *, measure=True):
        nonlocal after
        physical, tokens, tokhash = PROMPTS[nominal]
        before = after
        cache = cell.startswith('follow-up-')
        interval = native_task(tokens, nominal - 10 if cache else 0)
        server = first_cached_tasks(fixtures[interval['start']:interval['end']])[0]
        preceding = counters.copy()
        n_hits = 8 if seeded else 6
        for names, change in [(('demand_hits', 'decode_hits'), n_hits),
                              (('demand_misses', 'decode_misses'), 10 - n_hits)]:
            for key in names:
                counters[key] += change
        after = native('muse_cache_counters', counters)
        interval['end'] = after['end']
        generated = list(range(32))
        if bad_tokens and cell == 'first-request':
            generated.append(generated.pop(0))
        timing = 800 if seeded and (cell == 'first-request' or warm_gain and cell.startswith('warm-')) else 1000
        name = next((key for key, value in CELLS.items() if value[0] == cell), None)
        rows.append(dict(format='test-only', id=f'{cell}-{repeat}', status='complete', cell=cell, repeat=repeat,
            prompt_tokens=tokens, tokenized_prompt_tokens=tokens, nominal_prompt_tokens=nominal,
            cache_prompt=cache, n_predict=32, temperature=0, seed=1, ignore_eos=True,
            contract_request=name, measured_cell=measure, prompt_sha256=physical, token_ids_sha256=tokhash,
            output_token_ids=generated, generated_tokens=32, output_token_ids_sha256=token_digest(generated),
            source=interval, server_task=server, counters_before=before, counters_after=after,
            cache_counters={key: counters[key] - preceding[key] for key in NATIVE_COUNTERS},
            cache_hit_rate=n_hits / 10, decode_cache_hit_rate=n_hits / 10, prefill_cache_hit_rate=None,
            quiet={'included': True, 'observed_status': 'excluded', 'samples': [{}]},
            client_ttft_ms=timing, request_total_ms=2000,
            decode_tokens_per_second=10))

    request('first-request', 0, 512)
    warm = []
    for index in (1, 2):
        interval = native_task(511, 0)
        row = first_cached_tasks(fixtures[interval['start']:interval['end']])[0]
        text = f'warmup-{index}'
        warm.append(dict(index=index, status='complete', cache_prompt=False, measured_cell=False,
                         n_predict=32, generated_tokens=32, prompt=text, prompt_sha256=w2._sha(text),
                         token_ids_sha256=sha(f'warmup-tokens-{index}'.encode()), rendered_prompt_tokens=511,
                         server_log_start=interval['start'], server_log_end=interval['end'], server_request=row,
                         prompt_tokens=511, client_ttft_ms=1000, request_total_ms=1500, decode_tokens_per_second=11))
    warmup = dict(format=w2.FORMAT, status='complete', request_cap=6, stop_reason='stable',
                  decode_relative_tolerance=.10, requests=warm, target_tokens=511,
                  measured_prompt_sha256=[v[0] for v in PROMPTS.values()],
                  measured_token_ids_sha256=[v[2] for v in PROMPTS.values()])
    for repeat in range(3):
        for size in (512, 2048):
            request(f'warm-{size}', repeat, size)
            request(f'prime-{size}', repeat, size, measure=False)
            request(f'follow-up-{size}', repeat, size)
    if counter_tamper:
        rows[0]['cache_hit_rate'] = .999

    guard = dict(format='muse-r11-memory-watchdog/1', cap_bytes=96 * GIB,
                 threshold_rss_bytes=96 * GIB - (256 << 20), cgroup_verified=True, samples=50,
                 swap_bytes=0, peak_process_rss_bytes=95 * GIB, peak_memory_bytes=95 * GIB,
                 min_available_bytes=9 * GIB)
    policy = protocol['baseline']
    path = '/sealed/private/attachment'
    mapping = dict(path=path, sha256=PROFILE, mode='0400')
    configs = package['lab_task']['arms'][arm].get('env', {})
    physical = dict(configs, LLAMA_EXPERT_CACHE_NATIVE_PROFILE_PATH=path) if seeded else {}
    identity = 'load-' + arm
    peak = sum(value for key, value in DEVICE_MIB.items() if key != 'host_compute')
    load = dict(format='muse-r11-target-load/1', arm=arm, status='complete', load_id=identity,
                package_id=package['package_id'], request_id=REQUEST, delivery_check_id=DELIVERY['obs_id'],
                contract_sha256=CONTRACT_SHA, build_attempt_id='image-build', image_id=IMAGE, executable_sha256=EXEC,
                image_files_sha256={'llama-server': EXEC, 'libllama.so.1': 'e'*64, 'libggml-cuda.so.0': 'f'*64},
                library_delta=dict(parent_image_id=policy['image_id'], parent_library_sha256='0'*64,
                                   candidate_library_sha256='e'*64),
                profile_sha256=PROFILE, prefill_plan_sha256=policy['prefill_plan_sha256'],
                launch_config=policy['launch_config'], launch_config_sha256=policy['launch_config_sha256'],
                logical_env=configs, physical_env=physical, profile_mapping_before=mapping, profile_mapping_after=mapping,
                argv=['llama-server', '-m', 'pack', *policy['launch_config']['args']],
                pack={'bytes': 267200000000, 'manifest_sha256': policy['pack_manifest_sha256']},
                placement={'fit_margin_mib': 200}, observed={'device_mib': DEVICE_MIB},
                load_seconds=20 + fill * 40, device_peak_mib=peak, device_peak_categories_mib=DEVICE_MIB,
                device_peak_source=dict(path='server.log', start=0, ready_end=ready_end, end=len(fixtures)),
                device_budget_headroom_mib=110000-peak, memory_cap='96G',
                swap_cap_bytes=0, device_budget_mib=110000, peak_process_rss_bytes=guard['peak_process_rss_bytes'],
                peak_memory_bytes=guard['peak_memory_bytes'], min_available_bytes=guard['min_available_bytes'],
                watchdog=guard, gate_before_load={'ok': True, 'shared_admission': {'ok': True}},
                server_closed=True, started_utc='2026-11-27T17:00:00+00:00',
                ended_utc='2026-11-27T18:00:00+00:00')
    artifacts = {'load-receipts.json': load, 'warmup-receipts.json': warmup, 'startup-fill-receipts.json': startup,
                 'request-receipts.json': dict(format='muse-r11-requests/1', arm=arm, rows=rows),
                 'memory-watchdog.json': guard, 'server.log': bytes(fixtures)}
    sealed = {}
    for name, item in artifacts.items():
        raw = item if isinstance(item, bytes) else json.dumps(item).encode()
        sealed[name] = dict(data=raw, sha256=sha(raw), size=len(raw), artifact_id=f'{identity}-{name}')
    return dict(attempt=dict(attempt_id=identity, state='succeeded'),
                observation=dict(obs_id='capped-' + arm, values={'memory_cap': '96G'}), files=sealed)


def verdict(report):
    return next(row['verdict'] for row in report['checks'] if row['check'] == 'independent_acceptance')


def test_verified_target_report_keeps_all_samples_and_native_sources(tmp_path, package):
    arms = {arm: make_arm(package, arm) for arm in ARMS}
    report, measured, startup, comparison = evaluate(package, REQUEST, DELIVERY, arms, PROMPTS, set())
    assert report['outcome'] == 'completed' and verdict(report) == 'pass', report['checks']
    assert comparison['qualifying_warm_cells'] == ['p512', 'p2048']
    assert all(row['samples'] and len(row['samples']) == CELLS[row['request']][1]
               for row in report['results'] if row.get('request'))
    assert 'uploaded 53.00 GiB' in report['summary']
    output = tmp_path / 'report-stage'
    attachments = stage_report(output, REQUEST, package, report, arms, measured, startup, comparison)
    assert attachments['seeded-request-receipts.json'].read_bytes() == arms['AQBCE']['files']['request-receipts.json']['data']
    projected = json.loads(attachments['seeded-speed.json'].read_bytes())
    assert len(projected['rows']) == 13 and {row['cell'] for row in projected['rows']} == set(CELLS)
    assert json.loads(attachments['seeded-startup-fill.json'].read_bytes())['seed_fill_bytes'] == 53 * GIB

    mailbox = Mailbox(tmp_path / 'mailbox')
    mailbox.open_request(REQUEST, package)
    mailbox.post(REQUEST, 'factory', 'request',
                 {'package_id': package['package_id'], 'lab_task_id': 'lab-task', 'purpose': 'Test only'})
    reviewer = LabAgent(mailbox, name='unit-test-target', profile='spark-gb10')
    reviewer.accept(REQUEST)
    assert reviewer.check_report(REQUEST, report, attachments) == []
    reviewer.report(REQUEST, report, attachments)
    assert mailbox.thread(REQUEST)['state'] == 'reported'


def test_only_first_request_gain_does_not_earn_acceptance(package):
    arms = {arm: make_arm(package, arm, warm_gain=False) for arm in ARMS}
    report, _, _, comparison = evaluate(package, REQUEST, DELIVERY, arms, PROMPTS, set())
    assert comparison['first_request_only']
    assert verdict(report) == 'fail' and report['outcome'] == 'completed'
    assert 'confined to the first request' in report['summary']


def test_missing_arm_or_corrupted_native_counts_do_not_pass(package):
    off = make_arm(package, 'AQBC')
    partial, *_ = evaluate(package, REQUEST, DELIVERY, {'AQBC': off}, PROMPTS, set())
    assert partial['outcome'] == 'partial' and verdict(partial) == 'not_run'
    assert all(row['arm'] == 'AQBC' for row in partial['results'])
    corrupt = make_arm(package, 'AQBCE', counter_tamper=True)
    bad, *_ = evaluate(package, REQUEST, DELIVERY, {'AQBC': off, 'AQBCE': corrupt}, PROMPTS, set())
    assert verdict(bad) != 'pass'
    assert any('counter deltas' in row['detail'] for row in bad['checks'])


def test_all_tokens_are_matched_and_an_identity_mismatch_fails(package):
    arms = {'AQBC': make_arm(package, 'AQBC'), 'AQBCE': make_arm(package, 'AQBCE', bad_tokens=True)}
    report, *_ = evaluate(package, REQUEST, DELIVERY, arms, PROMPTS, set())
    assert verdict(report) == 'fail'
    assert sum(row['verdict'] == 'fail' for row in report['checks'] if row['check'] == 'token_identity') == 2
