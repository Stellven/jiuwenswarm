import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers.seeding_premise import (CELLS, TRACE_MANIFEST, Cache, Group, Lookup,  # noqa: E402
                                    canonical_digest, check_premise)


def make_request(tmp_path, *, shared_prompt=False, calibration_expert=0, legacy=False):
    def bound(name, value):
        path = tmp_path / name
        path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
        return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def record(projection, expert):
        data = [expert] if projection < 0 else [expert, 64]
        return struct.pack('<4i' + 'i' * len(data), 0, 1, 1, projection, *data)

    parent = bound('parent.json', {
        'parent': 'AQBC',
        'engine_source': {'commit': 'pinned'},
        'launch_config': {'args': ['--moe-cache-cpu-share', '0', '--moe-cache-mib', '1'],
                          'request': {'cache_prompt': True}},
    })
    # One layer, four experts, one tensor, four cache slots.
    header = struct.pack('<7I', 1, 1, 1, 0, 4, 1, 0)
    trace = (b'MCT1' if legacy else b'MCT2') + header + struct.pack('<2d3QIQ', 1, 1, 64, 64, 8, 1, 16)
    requests = []

    def append(cell, cohort, expert, index):
        nonlocal trace
        start = len(trace)
        trace += record(0, expert) + record(-1, expert)
        requests.append(dict(id=f'cell-{index}', cell=cell, cohort=cohort,
                             prompt_sha256=hashlib.sha256(str(index if not shared_prompt else 1).encode()).hexdigest(),
                             trace_start=start, trace_end=len(trace), prompt_n=64, generated_n=2,
                             cache_prompt=cohort == 'heldout'))

    for index, cell in enumerate(['first-request', 'warm-512', 'warm-2048', 'follow-up']):
        append(cell, 'heldout', 0, index)
    append('calibration', 'calibration', calibration_expert, 10)
    trace_ref = bound('trace.mct', trace)
    manifest = bound('manifest.json', {'format': TRACE_MANIFEST, 'parent_sha256': parent['sha256'],
                                      'trace_sha256': trace_ref['sha256'],
                                      'profiling_library_sha256': 'a' * 64, 'requests': requests})
    return {'parent': parent, 'trace': trace_ref, 'manifest': manifest}


def test_large_batch_hits_do_not_warm_or_promote_the_cache():
    cache = Cache(Group((0,), 8, (16,), 2), [(0, 1), (0, 3)])
    assert cache.lookup(Lookup(0, 0, 0, 0, 64, (0, 1))) == (1, 1)
    assert cache.clock[0] == 0
    assert cache.lookup(Lookup(0, 0, 0, -1, 1, (0,))) == (0, 1)
    assert cache.lookup(Lookup(0, 0, 0, -1, 1, (0, 3))) == (2, 0)


def test_no_headroom_is_a_verified_stop(tmp_path):
    request = make_request(tmp_path, calibration_expert=1)
    result = check_premise(request)
    assert result['done']
    premise = result['premise']
    assert not premise['may_build']
    assert premise['profile_sha256'] == canonical_digest(premise['profile'])
    assert set(premise['baseline']) == CELLS
    assert premise['baseline']['first-request']['host_bytes'] == 32
    assert premise['baseline']['first-request']['byte_hit_rate'] == 0
    assert premise['baseline']['warm-2048']['byte_hit_rate'] == 1


def test_calibration_seed_raises_first_request_byte_hit_rate(tmp_path):
    result = check_premise(make_request(tmp_path))
    assert result['done'] and result['premise']['may_build']
    premise = result['premise']
    assert premise['seeded']['first-request']['byte_hit_rate'] == 1
    assert premise['profile']['startup_upload_bytes'] == 16
    assert premise['avoided_host_bytes']['first-request'] == 32


def test_refuses_trace_without_read_only_branch_or_overlapping_prompts(tmp_path):
    assert not check_premise(make_request(tmp_path, legacy=True))['done']
    result = check_premise(make_request(tmp_path, shared_prompt=True))
    assert not result['done']
    assert 'distinct calibration prompts' in result['premise']['reason']
