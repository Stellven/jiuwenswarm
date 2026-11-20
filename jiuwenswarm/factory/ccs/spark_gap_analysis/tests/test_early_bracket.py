from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
from pathlib import Path
import sys

import pytest


BUNDLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUNDLE))
SPEC = importlib.util.spec_from_file_location('spark_gap_test_early', BUNDLE / 'run.py')
GAP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GAP)
from early_bracket import GATES, PROCESSES, prelaunch_resources


def test_nonquiet_screening_requires_only_the_evidenced_disjoint_lane():
    scope = 'residency-steady-30720-equivalent-stock-01'
    lane = dict(pid=12345, process='python3', cgroup='/app.slice/spark-c3-iteration2-do.service', cpus=[12, 19])
    check = dict({key: [] for key in PROCESSES}, quiet=False, screening_admitted=True,
                 screening_scope=scope, authorized_cpu_lane=[lane], load_1m=3.0, mem_available_gib=120)
    assert prelaunch_resources(check, scope) == [lane]
    with pytest.raises(ValueError, match='outside the owner-authorized'):
        prelaunch_resources(check)
    with pytest.raises(ValueError, match='disjoint CPU affinity'):
        prelaunch_resources(dict(check, authorized_cpu_lane=[dict(lane, cpus=[0, 12])]), scope)
    with pytest.raises(ValueError, match='Competing job'):
        prelaunch_resources(dict(check, factory_controllers=['unrelated']), scope)


def ref(name, value=None):
    return dict(artifact_id=name, sha256=hashlib.sha256(name.encode()).hexdigest(), value=value)


def fixture(cc):
    modes = ('strict-stock', 'stock', 'on', 'stock', 'strict-stock') if cc == 'C5' else ('stock', 'on', 'stock')
    expected = dict(stock_mode='stock', nested_strict=cc == 'C5', label='synthetic-test')
    source = dict(path='/fixture/model', resolved_path='/fixture/model', identity=dict(inode=111, size=8192, mtime_ns=99))
    rows, scopes = [], []
    for size in (512, 2048):
        rows.append(dict(target_tokens_including_template=size, prompt_sha256=ref(str(size))['sha256']))

    for i, mode in enumerate(modes):
        def stamp(seconds):
            baseline = datetime(2026, 11, 20, tzinfo=timezone.utc) + timedelta(minutes=i+1, seconds=seconds)
            return baseline.isoformat()

        tag = f'scope-{i}'
        cgroup = f'/sys/fs/cgroup/test-{i}'
        label = f'{cc}-{mode}-early'
        result_path = '/' + tag
        gate = {GATES[cc]: '1'} if mode == 'on' else {}
        if cc == 'C1' and mode == 'on':
            gate = {GATES[cc]: result_path + '/events.jsonl'}
        binary = ref('candidate' if mode == 'on' else 'stock')['sha256']
        command = [binary, '-m', '/fixture/model']
        expected[mode] = dict(command=command, gates=gate, library_path='/libs', source_commit=binary, binary_sha256=binary,
                              products_manifest_sha256=ref('inventory')['sha256'])
        quiet = {key: [] for key in PROCESSES} | dict(quiet=True, load_1m=0.2, mem_available_gib=120)
        start = dict(arm=label, binary_sha256=binary, result_path=result_path, unit=tag, command=command,
                     memory_max=100 * 1024**3, cpus='0-7', start=stamp(0), launch_environment={'LD_LIBRARY_PATH': '/libs', **gate})
        stop = dict(start, stop=stamp(45), min_mem_available_bytes=20 * 1024**3, peak_memory_bytes=80 * 1024**3,
                    reason=None, returncode=0, scope_verified=True, memory_events={'max': '30', 'oom': '0'})
        controls = {'memory.max': str(100 * 1024**3), 'memory.swap.max': '0', 'memory.oom.group': '1',
                    'cpu.max': '800000 100000', 'sched_affinity': list(range(8))}
        page = dict(schema='spark-source-residency/1', page_size=4096, pages_per_sample=4096, seed=20261120,
                    views={'llama': {'files': [source], 'total': {'expert': {'estimated_resident_fraction': 0.2}}}},
                    scope_accounting={'path': cgroup})
        conditioning = dict(schema='spark-source-cache-conditioning/1', method='file-specific POSIX_FADV_DONTNEED', quiet=quiet,
                            before=dict(page, started=stamp(-4)), after=dict(page, completed=stamp(-2)))
        captures, hashes = [], {}
        for j, (repeat, size) in enumerate(((0, 512), (0, 2048), (1, 512), (1, 2048))):
            name = f'{tag}-request-{j}'
            moment = 3 + 7*j
            request = dict(messages=[{'role': 'user', 'content': str(size)}], max_tokens=32,
                           cache_prompt=False, stream=True, temperature=0, seed=1, chat_template_kwargs={'enable_thinking': False})
            output = ref(f'output-{size}' + ('-strict' if mode == 'strict-stock' else ''))
            reason = ref('reasoning')
            hashes[str(size)] = [output['sha256'], reason['sha256']]
            resources = ref(name+'-resources', dict(schema='spark-request-resources/1', cgroup=cgroup,
                                                  snapshots={'start': {}, 'first_token': {}, 'end': {}}))
            result = dict(arm=label, prompt_tokens=size, repeat=repeat, discard=not repeat, ok=True,
                          started=stamp(moment), ttft_s=2.0 if mode == 'on' else 4.0+i, decode_tps=3.0,
                          prompt_sha256=ref(str(size))['sha256'], timings={'cache_n': 0},
                          usage=dict(prompt_tokens=size, completion_tokens=32, prompt_tokens_details={'cached_tokens': 0}),
                          output_sha256=output['sha256'], reasoning_sha256=reason['sha256'], resource_windows_sha256=resources['sha256'])
            captures.append(dict(result=ref(name+'-result', result), request=ref(name+'-request', request),
                before=ref(name+'-before', dict(quiet, observed_utc=stamp(moment-1))),
                after=ref(name+'-after', dict(quiet, observed_utc=stamp(moment+2))), request_resources=resources,
                output=output, reasoning=reason, response=ref(name+'-sse'), residency=ref(name+'-pages', dict(page, completed=stamp(moment-0.5)))))
        markers = {'active': ['active'] if mode == 'on' else [], 'inactive': [], 'stats': ['stats decisions=2'] if mode == 'on' else []}
        settings = dict(n_ctx=4096, n_ctx_seq=4096, n_batch=2047, n_ubatch=512,
                        n_slots=4 if mode == 'strict-stock' else 1, n_threads=8, n_threads_batch=8)
        scope = dict(start=ref(tag+'-start', start), stop=ref(tag+'-stop', stop),
                     scope=ref(tag+'-scope', {'actual': controls, 'cgroup': cgroup}),
                     probe=ref(tag+'-probe', dict(cc=cc, mode=mode, window='early', result_dir=result_path, greedy_hashes=hashes)),
                     quiet=dict(ref(tag+'-quiet', quiet), mtime_utc=stamp(-1)), conditioning=ref(tag+'-conditioning', conditioning),
                     load=ref(tag+'-load', {'source_commit': binary, 'ready_at': stamp(1), 'health_elapsed_s': 1.0,
                                          'products_manifest_sha256': ref('inventory')['sha256']}),
                     log=dict(ref(tag+'-log'), markers=markers, effective_settings=settings), requests=captures)
        if cc == 'C1' and mode == 'on':
            scope['recorder'] = dict(raw=ref(tag+'-events'), summary=ref(tag+'-summary', dict(type='summary', expected=10, written=10)))
        scopes.append(scope)
    return dict(mode='early-bracket', cc=cc, expected=expected, scopes=scopes,
                model_identity=ref('model', {'files': [dict(path=source['path'], size=8192, mtime_ns=99)]}),
                prompt_manifest=ref('prompts', {'prompts': rows}), profile_ref=ref('profile'))


@pytest.mark.parametrize('cc', list(GATES))
def test_matches_brackets_and_c5_settings_parity_is_separate(cc):
    analyzed = GAP.analyze(fixture(cc))
    assert analyzed['candidate_activation']
    assert len(analyzed['scopes']) == (5 if cc == 'C5' else 3)
    for cell in analyzed['measurements']:
        assert cell['candidate_s'] == 2
        assert cell['matched_greedy_parity']
        assert cell['interpretation'] == 'lower than both stock endpoints'
        assert 'conditional_ci95' not in cell
        if cc == 'C5':
            assert cell['settings_comparison']['strict_greedy_parity']
            assert not cell['settings_comparison']['cross_settings_greedy_parity']


def test_contamination_and_unexpected_safety_events_refused():
    evidence = fixture('C3')
    contaminated = deepcopy(evidence)
    contaminated['scopes'][1]['requests'][2]['after']['value']['test_processes'] = ['pytest']
    with pytest.raises(ValueError, match='Competing job'):
        GAP.analyze(contaminated)
    evidence['scopes'][1]['stop']['value']['memory_events']['oom_kill'] = '1'
    with pytest.raises(ValueError, match='safety event'):
        GAP.analyze(evidence)


def test_matched_candidate_greedy_divergence_retains_timing():
    evidence = fixture('C5')
    middle = evidence['scopes'][2]
    altered = ref('changed-512')
    for row in middle['requests']:
        if row['result']['value']['prompt_tokens'] == 512:
            row['result']['value']['output_sha256'] = altered['sha256']
            row['output'] = altered
    middle['probe']['value']['greedy_hashes']['512'][0] = altered['sha256']
    cells = GAP.analyze(evidence)['measurements']
    assert not cells[0]['attribution_eligible']
    assert cells[0]['candidate_s'] == 2
    assert cells[1]['attribution_eligible']


def test_mapper_startup_marker_without_split_decisions_does_not_establish_activity():
    evidence = fixture('C5')
    evidence['scopes'][2]['log']['markers']['stats'] = ['stats decisions=0 rows=0 bypasses=3']
    result = GAP.analyze(evidence)
    assert not result['candidate_activation']
    assert all(not cell['attribution_eligible'] for cell in result['measurements'])
