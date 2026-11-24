import hashlib
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('gap_analysis', Path(__file__).resolve().parents[1] / 'run.py')
GAP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GAP)


def ref(name):
    return {'artifact_id': name, 'sha256': hashlib.sha256(name.encode()).hexdigest()}


def tiny_abba():
    manifest = dict(ref('manifest'), value={'prompts': [
        {'target_tokens_including_template': n, 'prompt_sha256': ref(str(n))['sha256']} for n in GAP.PROMPTS]})
    scopes, requests = [], []
    for i, arm in enumerate(('A', 'S', 'S', 'A')):
        def stamp(minute, second):
            return f'2026-11-20T09:{minute:02}:{second:02}+00:00'

        scope = ref(f'scope-{i}')
        scopes.append(dict(scope, arm=arm, load=dict(ref(f'load-{i}'), seconds=1.0),
                           quiet_preflight=dict(ref(f'quiet-{i}'), quiet=True),
                           value=dict(start=stamp(i, 0), stop=stamp(i, 50), returncode=0, scope_verified=True,
                                      memory_max=GAP.CEILING, cpus='0-7', binary_sha256=ref(arm)['sha256'],
                                      memory_events={'oom': '0', 'oom_kill': '0'})))
        repeats = (0, 0, 1, 2) if i < 2 else (0, 0, 3, 4, 5)
        for step, repeat in enumerate(repeats):
            for offset, prompt in enumerate(GAP.PROMPTS if repeat == 0 or repeat % 2 else GAP.PROMPTS[::-1]):
                name = f'scope-{i}-step-{step}-prompt-{prompt}'
                result = dict(arm=arm, prompt_tokens=prompt, repeat=repeat, discard=repeat == 0,
                              started=stamp(i, 1 + step * 2 + offset), ok=True, ttft_s=2.0 if arm == 'A' else 1.0,
                              usage=dict(prompt_tokens=prompt, completion_tokens=32, prompt_tokens_details={'cached_tokens': 0}),
                              timings={'cache_n': 0}, prompt_sha256=ref(str(prompt))['sha256'], output_sha256=ref('output')['sha256'])
                request = dict(messages=[{'role': 'user', 'content': str(prompt)}], max_tokens=32,
                               cache_prompt=False, stream=True, temperature=0, seed=1)
                requests.append(dict(ref(name), result=result, request=request, request_ref=ref(name + '-request'),
                                     scope_id=scope['artifact_id']))
    return dict(mode='p4-abba', prompt_manifest=manifest, scopes=scopes, requests=requests)


def test_matched_two_window_bootstrap():
    analysis = GAP.analyze(tiny_abba())
    assert len(analysis['eligible']) == 20
    assert len(analysis['excluded']) == 16
    cell = next(r for r in analysis['measurements'] if r['arm'] == 'S')
    assert cell['comparisons']['inverse_ttft_vs_A'] == {'estimate': 2, 'conditional_ci95': [2, 2]}
    assert cell['comparisons']['gap_closed'] == {'estimate': 1, 'conditional_ci95': [1, 1]}


def test_reconnaissance_suppresses_intervals_and_rejects_cache_use():
    evidence = tiny_abba()
    evidence['requests'][4]['result']['timings']['cache_n'] = 1
    with pytest.raises(ValueError, match='matched warmups or measured repeats'):
        GAP.analyze(evidence)
    evidence['mode'] = 'p1-reconnaissance'
    analysis = GAP.analyze(evidence)
    assert len(analysis['eligible']) == 19
    assert 'conditional_ci95' not in analysis['measurements'][0]['comparisons']['gap_closed']

def test_five_pairs_in_each_pass_against_same_budget_control():
    from copy import deepcopy
    data = tiny_abba()
    requests = []
    for index, scope in enumerate(data['scopes']):
        templates = {row['result']['prompt_tokens']: row for row in data['requests']
                     if row['scope_id'] == scope['artifact_id']}
        scope['arm'] = 'A+' if index in (0, 3) else 'C3'
        order = [((512, 2048), 0), ((512, 2048), 0), ((2048, 512), 0)]
        for pair in range(5):
            repeat = (1 if index < 2 else 6) + pair
            order.append(((512, 2048) if pair % 2 == 0 else (2048, 512), repeat))
        for position, (n, repeat) in enumerate((n, repeat) for sizes, repeat in order for n in sizes):
            row = deepcopy(templates[n])
            row.update(ref(f'{index}-{position}-result'))
            row['result'].update(arm=scope['arm'], repeat=repeat, discard=repeat == 0,
                                 started=f'2026-11-20T09:{index:02}:{position + 1:02}+00:00',
                                 ttft_s=4 if scope['arm'] == 'C3' else 6,
                                 decode_tps=20 if scope['arm'] == 'C3' else 19)
            requests.append(row)
    data['requests'] = requests
    analysis = GAP.analyze(data)
    cell = next(row for row in analysis['measurements'] if row['arm'] == 'C3')
    assert cell['n'] == 10
    assert len(analysis['excluded']) == 24
    assert cell['comparisons']['inverse_ttft_vs_Aplus']['estimate'] == 1.5
    for key, estimate in [('paired_ttft_seconds_saved_vs_Aplus', 2), ('paired_decode_tps_gained_vs_Aplus', 1)]:
        assert cell['comparisons'][key] == dict(estimate=estimate, observed_range=[estimate, estimate],
                                                pass_medians=[estimate, estimate], conditional_ci95=[estimate, estimate])
