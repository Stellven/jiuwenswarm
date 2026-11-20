from base64 import b64encode
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest
import yaml


BUNDLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUNDLE))
SPEC = importlib.util.spec_from_file_location('spark_gap_direct_seed_test', BUNDLE / 'run.py')
GAP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GAP)
from direct_seed import DIRECT, DIRECT_GATE, PROFILE, PROFILE_GATE, PROFILE_PATH
from early_bracket import PROCESSES
from residency_speed import steady_order


def ref(name, value=None):
    return dict(artifact_id=name, sha256=hashlib.sha256(name.encode()).hexdigest(), value=value)


def timestamp(arm_index, seconds):
    start = datetime(2026, 11, 20, tzinfo=timezone.utc) + timedelta(minutes=2 * arm_index)
    return (start + timedelta(seconds=seconds)).isoformat()


def engine_log(seed_source=None, slot=0, transferred=4096):
    rows = [
        'CUDA0 MoE cache size = 30610.00 MiB for 123456.00 MiB of host experts, 0.0% of the misses on the CPU',
        'llama_moe_cache: ubatch <= 8: hits = 2, misses = 1 (0 on the CPU), hit rate = 66.6%, uploaded = 4.00 MiB',
        'llama_moe_cache: large batches: 10 experts copied from the cache, 40.00 MiB',
    ]
    if seed_source is None:
        return rows
    for layer in range(40):
        for expert in range(192):
            admitted = (layer, expert) == (0, 0)
            rows.append(f'{PROFILE} nomination group=0 layer={layer} rank={expert} expert={expert}'
                        f' admitted={int(admitted)} reason=within_grant slot={slot if admitted else -1} complete_charge=4096')
    rows += [f'{PROFILE} active seeds=1 initial_h2d_bytes=4096 init_us=100 charged_bound=10000'
             f' policy=stock_evictable reverse_rank=1 seed_source={seed_source}',
             f'{PROFILE} stats active=1 seeds=1 planned_seed_payload_bytes=4096 init_us=100 charged_bound=10000 demand_source=mmap']
    if seed_source == 'direct':
        rows.append(f'{DIRECT} stats state=complete scope=startup_seed_payload planned_payload_bytes=4096'
                    f' requested_io_bytes=4608 returned_io_bytes=4608 direct_payload_bytes=4096 uploaded_payload_bytes={transferred}'
                    ' alignment_overhead_bytes=512 staging_bytes=1048576 memory_alignment_max=4 read_alignment_max=512'
                    ' files=1 calls=1 failures=0 fallback_count=0 elapsed_us=101')
    return rows


def fixture(variant=None):
    source = dict(path='/fixture/model.gguf', resolved_path='/fixture/model.gguf',
                  identity=dict(inode=111, size=8192, mtime_ns=99))
    model = ref('model', {'files': [dict(path=source['path'], size=8192, mtime_ns=99)]})
    profile = ref('profile', {'layers': [dict(layer=layer, expert_ids=list(range(192))) for layer in range(40)]})
    prompts = ref('prompts', {'prompts': [dict(target_tokens_including_template=size, prompt_sha256=ref(str(size))['sha256'])
                                        for size in (512, 2048)]})
    regions = ref('source-regions')
    quiet = dict({key: [] for key in PROCESSES}, quiet=True, load_1m=0.2, mem_available_gib=120)
    flags = ['-m', source['path'], '-lm', 'mmap', '--cpu-moe', '--moe-cache-mib', '30720', '--moe-cache-cpu-share', '0']
    controls = {'memory.max': str(GAP.CEILING), 'memory.swap.max': '0', 'memory.oom.group': '1',
                'cpu.max': '800000 100000', 'sched_affinity': list(range(8))}
    settings = dict(n_ctx=4096, n_ctx_seq=4096, n_batch=2048, n_ubatch=512, n_slots=1, n_threads=8, n_threads_batch=8)
    scopes, expected, classes = [], [], {}
    def bound(moment, pid):
        return dict(monotonic_ns=moment, processes={str(pid): dict(comm='llama-server', starttime_ticks=10,
                   io={'read_bytes': moment * 4096}, majflt=moment)}, memory_stat={'workingset_refault_file': moment},
                   host_disks={'nvme0n1': dict(dev='259:0', read_bytes=moment * 8192)})

    for i, (role, mode, seed_source) in enumerate((
        ('A+', 'equivalent-stock', None), ('02b-mmap', 'off', 'mmap'), ('02b-direct', 'on', 'direct'),
    )):
        binary = ref('02b-elf' if seed_source else 'stock-elf')['sha256']
        label = role + '-speed-30720MiB'
        tag = 'scope-' + str(i)
        cgroup = '/sys/fs/cgroup/' + tag
        pid = 400 + i
        gates = {PROFILE_GATE: '1', PROFILE_PATH: '/fixture/profile.json'} if seed_source else {}
        if seed_source == 'direct':
            gates[DIRECT_GATE] = '1'
        command = [binary, *flags]
        build = 'build-receipt-02b' if seed_source else None
        expected.append(dict(label=label, command=command, gates=gates, library_path='/libs', binary_sha256=binary,
                             source_commit=binary, products_manifest_sha256=ref('inventory')['sha256'],
                             profile_sha256=profile['sha256'], build_receipt=build))
        start = dict(arm=label, binary_sha256=binary, result_path='/' + tag, unit=tag, command=command,
                     memory_max=GAP.CEILING, cpus='0-7', start=timestamp(i, 0), launch_environment={'LD_LIBRARY_PATH': '/libs', **gates})
        stop = dict(start, stop=timestamp(i, 90), min_mem_available_bytes=20 * 1024**3, peak_memory_bytes=80 * 1024**3,
                    reason=None, returncode=0, scope_verified=True, memory_events={'max': '30', 'oom': '0'})
        group = dict(files=[source], total={name: dict(estimated_resident_fraction=0) for name in ('expert', 'dense', 'engram')})
        snapshot = dict(schema='spark-source-residency/1', page_size=4096, pages_per_sample=4096, seed=20261120,
                        scope_accounting=dict(path=cgroup, stat_bytes={'file': 123}), views=dict(llama=group, strata=group))
        condition = dict(schema='spark-source-cache-conditioning/1', method='file-specific POSIX_FADV_DONTNEED',
                         quiet=quiet, regions_sha256=regions['sha256'],
                         before=dict(snapshot, started=timestamp(i, -4)), after=dict(snapshot, completed=timestamp(i, -2)))
        logs = engine_log(seed_source, slot=int(i == 2 and variant == 'slot'), transferred=4000 if i == 2 and variant == 'upload' else 4096)
        raw = '\n'.join(logs).encode()
        log = dict(ref(tag + '-log'), sha256=hashlib.sha256(raw).hexdigest(), effective_settings=settings,
                   gzip_b64=b64encode(gzip.compress(raw, mtime=0)).decode())
        requests, hashes = [], {'512': [], '2048': []}
        for j, pos in enumerate(steady_order()):
            name, size, repeat = (pos[key] for key in ('path', 'size', 'repeat'))
            tag_request = f'{tag}-{name}'
            moment = 4 + 4 * j
            output = ref(f'output-{size}' if variant != 'parity' or i != 2 else f'changed-{size}')
            reasoning = ref('reasoning')
            request = dict(messages=[{'role': 'user', 'content': str(size)}], max_tokens=32,
                           cache_prompt=False, stream=True, temperature=0, seed=1, chat_template_kwargs={'enable_thinking': False})
            resources = ref(tag_request+'-phases', dict(schema='spark-request-resources/1', cgroup=cgroup,
                        snapshots={name: bound(moment*3+k, pid) for k, name in enumerate(('start', 'first_token', 'end'))}))
            result = dict(arm=label, prompt_tokens=size, repeat=repeat, discard=not repeat, ok=True,
                          started=timestamp(i, moment), ttft_s=float(5-i), decode_tps=float(18+i),
                          prompt_sha256=ref(str(size))['sha256'], timings={'cache_n': 0},
                          usage=dict(prompt_tokens=size, completion_tokens=32, prompt_tokens_details={'cached_tokens': 0}),
                          output_sha256=output['sha256'], reasoning_sha256=reasoning['sha256'],
                          resource_windows_sha256=resources['sha256'])
            requests.append(dict(result=ref(tag_request+'-result', result), request=ref(tag_request+'-request', request),
                before=ref(tag_request+'-before', dict(quiet, observed_utc=timestamp(i, moment-1))),
                after=ref(tag_request+'-after', dict(quiet, observed_utc=timestamp(i, moment+2))),
                request_resources=resources, output=output, reasoning=reasoning, response=ref(tag_request+'-stream'),
                residency=ref(tag_request+'-residency', dict(snapshot, completed=timestamp(i, moment-0.5)))))
            hashes[str(size)].append([output['sha256'], reasoning['sha256']])
        protocol = dict(schema='spark-cold-steady/1', arm=label, view='llama', source_reset='file-specific DONTNEED',
                        regions_sha256=regions['sha256'], warmups_per_size=3, measured_per_size=5, ordered_requests=steady_order())
        scope = dict(start=ref(tag+'-start', start), stop=ref(tag+'-stop', stop), log=log, requests=requests,
                     scope=ref(tag+'-scope', dict(actual=controls, cgroup=cgroup, pid=pid)),
                     probe=ref(tag+'-probe', dict(cc='C3', mode=mode, window='speed', result_dir='/' + tag, greedy_hashes=hashes)),
                     quiet=dict(ref(tag+'-quiet', quiet), mtime_utc=timestamp(i, -1)), conditioning=ref(tag+'-condition', condition),
                     load=ref(tag+'-load', dict(source_commit=binary, ready_at=timestamp(i, 1), health_elapsed_s=1.0,
                              products_manifest_sha256=ref('inventory')['sha256'], native_build_receipt=build)),
                     protocol=ref(tag+'-protocol', protocol))
        if seed_source:
            active = next(row for row in logs if row.startswith(PROFILE + ' active'))
            fields = dict(sha256=profile['sha256'], marker=active, seed_source=seed_source)
            if seed_source == 'direct':
                fields['direct_seed_stats'] = logs[-1].split(DIRECT + ' stats ', 1)[1]
            scope['activation'] = ref(tag+'-activation', fields)
        scopes.append(scope)
        labels = ['post-conditioning', 'post-ready', *(row['path'] for row in steady_order()[1:])]
        classes[role] = [GAP.reference(item) | {'label': label} for label, item in zip(
            labels, [scope['conditioning'], *(row['residency'] for row in requests)], strict=True)]
    if variant == 'gate':
        expected[-1]['gates'] = expected[1]['gates']
    if variant == 'snapshot':
        classes['02b-direct'][1]['artifact_id'] = 'different-residency'
    return dict(mode='c3-direct-seed-30g', profile=profile, prompts=prompts, regions=regions, model_identity=model,
                expected=expected, scopes=scopes, expert_classes=ref(
                    'hot/other', dict(admitted_layer_expert_ids=[[0, 0]], startup_upload_bytes=4096, scopes=classes)))


def test_registered_direct_seed_mode_covers_three_arms():
    declared = yaml.safe_load((BUNDLE / 'cc.yaml').read_text())
    assert declared['version'] == '1.6.0'
    assert set(declared['capabilities']) == {'analyze', 'verify'}
    analysis = GAP.analyze(fixture())
    assert analysis['mode'] == 'c3-direct-seed-30g'
    assert analysis['exact_greedy_parity']
    aplus, mmap, direct = analysis['scopes']
    assert aplus['seed'] is None
    assert mmap['seed']['admitted_slots_sha256'] == direct['seed']['admitted_slots_sha256']
    assert direct['seed']['direct_io']['uploaded_payload_bytes'] == 4096
    assert [(r['candidate'], r['control']) for r in analysis['comparisons']] == [
        ('02b-direct', '02b-mmap'), ('02b-direct', 'A+'), ('02b-mmap', 'A+')]
    direct_minus_mmap = analysis['comparisons'][0]
    assert len(direct_minus_mmap['cold_pairs']) == 6
    assert [row['n'] for row in direct_minus_mmap['steady']] == [5, 5]
    assert all(row['ttft_delta_s']['median'] == -1 and row['decode_gain_tps']['median'] == 1
               for row in direct_minus_mmap['steady'])


@pytest.mark.parametrize(('variant', 'reason'), [
    ('gate', 'exact same-binary buffered/direct gate'),
    ('upload', 'completed exact I/O and upload counters'),
    ('slot', 'Actual native bank, exact admitted slots/bytes'),
    ('parity', 'greedy parity differs'),
    ('snapshot', 'Seeded source-page classes differ'),
])
def test_refuses_mismatched_direct_attempts(variant, reason):
    with pytest.raises(ValueError, match=reason):
        GAP.analyze(fixture(variant))
