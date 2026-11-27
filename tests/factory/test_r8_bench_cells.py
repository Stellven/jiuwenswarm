"""Exercise the approved bench protocol with fake server and quiet evidence."""

import hashlib
import io
import json
from types import SimpleNamespace

import pytest

from jiuwenswarm.factory.capped_run import RunError
from scripts.factory import lab_v4_fast, lab_v4_quiet, r8_bench_cells


@pytest.fixture
def bench(tmp_path):
    counts = dict(zip(r8_bench_cells.PROMPTS, (127, 511, 1023, 2047, 4095)))
    prompts, cells = {}, []
    for name, count in counts.items():
        path = tmp_path / name
        raw = f'{name}\r\n'.encode()
        path.write_bytes(raw)
        prompts[name] = dict(file=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                             verified_server_tokens=count if name in {'p512', 'p2048'} else None)
        cells.extend(dict(prompt=name, state='cold' if repeat == 0 else 'warm', repeat=repeat,
                          n_predict=32, evict_pages=repeat == 0) for repeat in range(3))
    decode = dict(prompt='p512', state='warm', repeat=0, n_predict=128, evict_pages=False, role='decode')
    historical = [*cells[:6], decode, *cells[6:]]
    leg = dict(id='1', role='P', pack='MIXED', ctx=8192, batch=2048, ubatch=512,
               moe_cache_mib=61440, request_plan='speed')
    proposal = dict(speed_prompt_pins=prompts, request_plans=dict(speed=historical, final=cells),
                    memory=dict(device_budget_mib=110000),
                    engine=dict(required_verified_image_id='engine', required_image_executable_sha256='binary'),
                    pack_pins={'MIXED': dict(first_shard=str(tmp_path / 'pack.gguf'), manifest_sha256='manifest')})
    return SimpleNamespace(counts=counts, proposal=proposal, leg=leg, out=tmp_path)


def fake_server(bench, model=35000, compute=1500, *, bad_generation=False):
    log = bench.out / 'server.log'
    log.write_text(f'''llama_context: n_ctx = 8192
llama_context: n_batch = 2048
llama_context: n_ubatch = 512
CUDA0 model buffer size = {model}.00 MiB
CUDA0 KV buffer size = 1500.00 MiB
CUDA0 compute buffer size = {compute}.00 MiB
CUDA_Host compute buffer size = 20000.00 MiB
CUDA0 MoE cache size = 61438.50 MiB
''')
    events = []

    def post(body, *, path='/completion', consume=json.load, timeout=7200):
        events.append((path, body))
        if path == '/tokenize':
            assert body['add_special'] is True and body['parse_special'] is True
            assert body['content'].endswith('\r\n')
            return dict(tokens=list(range(bench.counts[body['content'].strip()])))
        assert body['ignore_eos'] is True and body['cache_prompt'] is False and body['return_progress'] is True
        count = bench.counts[body['prompt'].strip()]
        generated = body['n_predict'] - (bad_generation and len(events) == 6)
        frames = [
            dict(prompt_progress=dict(processed=count - 4, cache=0, total=count)),
            dict(prompt_progress=dict(processed=count, cache=0, total=count)),
            dict(content='Example'),
            dict(stop=True, timings=dict(prompt_n=count, prompt_ms=42, prompt_per_second=9,
                                         predicted_n=generated, predicted_per_second=2.5)),
        ]
        return consume(io.BytesIO(''.join(f'data: {json.dumps(frame)}\n\n' for frame in frames).encode()))

    return SimpleNamespace(log=log, ready_s=29, proc=SimpleNamespace(pid=-1), post=post, events=events,
                           run=SimpleNamespace(peak=100, low=80))


class Quiet:
    limits = {}

    def __init__(self, fail_gate=False):
        self.samples = []
        self.fail_gate = fail_gate

    def wait(self, phase, following, log):
        if self.fail_gate:
            self.samples.append(dict(phase='start_wait', reasons=['resident-server machine gate closed']))
            raise RunError('MACHINE_BUSY', 'resident-server machine gate closed')
        self.samples.append(dict(phase=phase, reasons=[]))
        return len(self.samples) - 1, False

    def mark(self, phase, following):
        self.samples.append(dict(phase=phase, reasons=[]))
        return len(self.samples) - 1


def test_speed_keeps_independent_repeats_and_excluded_rows(bench, monkeypatch):
    server = fake_server(bench, bad_generation=True)
    monkeypatch.setattr(lab_v4_fast, 'evict', lambda model: server.events.append(('evict', model)))
    monkeypatch.setattr(lab_v4_quiet, 'evidence_issues',
                        lambda samples, limits: ['foreign test process present'] if len(server.events) == 8 else [])
    real_post = server.post

    def post(body, **kwargs):
        if 'prompt' in body:
            written = json.loads((bench.out / '1.speed.json').read_text())
            completed = sum(path == '/completion' for path, _ in server.events)
            assert len(written['rows']) == completed
        return real_post(body, **kwargs)

    server.post = post
    # Count the first timed completion after five tokenizations and the first eviction.
    bench.leg['request_plan'] = 'final'
    report = r8_bench_cells.speed(server, Quiet(), bench.proposal, bench.out, bench.leg, {})
    assert report['status'] == 'completed'
    assert len(report['rows']) == 15
    assert [row['repeat'] for row in report['rows'] if row['request'] == 'p512'] == [0, 1, 2]
    assert sum(path == 'evict' for path, _ in server.events) == 5
    assert [path for path, _ in server.events[:5]] == ['/tokenize'] * 5
    assert report['rows'][1]['quiet']['status'] == 'excluded'
    assert report['rows'][0]['prefill_segment_tokens'] == [123, 4]
    assert report['rows'][0]['output_sha256'] == hashlib.sha256(b'Example').hexdigest()
    assert report['rows'][0]['tokenized_prompt_tokens'] == report['rows'][0]['prompt_tokens'] == 127
    assert report['rows'][0]['pack_manifest_sha256'] == 'manifest'
    assert report['rows'][0]['decode_tokens_per_second'] == 2.5
    assert json.loads((bench.out / '1.speed.json').read_text()) == report


def test_speed_stops_and_persists_failed_gate_admission(bench, monkeypatch):
    server = fake_server(bench)
    monkeypatch.setattr(lab_v4_fast, 'evict', lambda model: None)
    with pytest.raises(RunError, match='resident-server machine gate closed'):
        r8_bench_cells.speed(server, Quiet(fail_gate=True), bench.proposal, bench.out, bench.leg, {})
    report = json.loads((bench.out / '1.speed.json').read_text())
    assert report['status'] == 'stopped'
    assert report['error']['code'] == 'MACHINE_BUSY'
    assert len(report['rows']) == 1
    assert report['rows'][0]['quiet']['status'] == 'excluded'
    assert not any(path == '/completion' for path, _ in server.events)


def test_actual_generation_mismatch_is_excluded_and_next_cell_continues(bench, monkeypatch):
    server = fake_server(bench, bad_generation=True)
    monkeypatch.setattr(lab_v4_fast, 'evict', lambda model: None)
    monkeypatch.setattr(lab_v4_quiet, 'evidence_issues', lambda samples, limits: [])
    report = r8_bench_cells.speed(server, Quiet(), bench.proposal, bench.out, bench.leg, {})
    assert report['rows'][0]['generated_tokens'] == 31
    assert report['rows'][0]['quiet']['status'] == 'excluded'
    assert report['rows'][1]['generated_tokens'] == 32
    assert len(report['rows']) == 16
    assert [(r['request'], r['n_predict']) for r in report['rows'] if r['role'] == 'decode'] == [('p512', 128)]


def test_speed_schedule_a_has_one_warm_4096_and_checks_prompt_hash(bench):
    bench.leg['role'] = 'A'
    bench.proposal['request_plans']['speed'].pop()
    assert len(r8_bench_cells.speed_schedule(bench.proposal, bench.leg)) == 15
    bench.proposal['speed_prompt_pins']['p128']['sha256'] = 'bad'
    with pytest.raises(ValueError, match='p128.*SHA-256'):
        r8_bench_cells.read_prompts(bench.proposal)


@pytest.mark.parametrize('model, expected_cache', [(35000, 66560), (37900, 62464)])
def test_calibration_preserves_delivered_batch_and_fits_cache(bench, model, expected_cache):
    server = fake_server(bench, model=model)
    bench.leg['target_plan'] = dict(batch=2048, ubatch=2048, moe_cache_mib=66560, headroom_mib=2048)
    plan = r8_bench_cells.calibration(server, bench.proposal, bench.out, bench.leg)
    assert (plan['batch'], plan['ubatch'], plan['moe_cache_mib']) == (2048, 2048, expected_cache)
    assert plan['micro_batches']['4095'] == {'before': 8, 'after': 2}
    assert plan['estimate_mib'] <= plan['device_budget_mib']
    assert [path for path, _ in server.events] == ['/tokenize'] * 5
    receipt = json.loads((bench.out / '1.calibration.json').read_text())
    assert receipt['observed_settings']['device_mib']['host_compute'] == 20000
    assert json.loads((bench.out / '1.plan.json').read_text()) == plan


def test_nvfp4_calibration_keeps_reference_cache(bench):
    server = fake_server(bench, model=37000, compute=1000)
    bench.leg.update(id='2', role='A+P calibration')
    plan = r8_bench_cells.calibration(server, bench.proposal, bench.out, bench.leg)
    assert (plan['batch'], plan['ubatch'], plan['moe_cache_mib']) == (4096, 4096, 61440)
    assert plan['prompt_tokens'] == list(bench.counts.values())


def test_ttft_starts_at_generated_content_after_progress_and_empty_token(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(lab_v4_fast.time, 'monotonic', lambda: clock[0])
    events = [
        (10.01, dict(content='', tokens=[-1], prompt_progress=dict(processed=0))),
        (15.00, dict(content='', tokens=[-1], prompt_progress=dict(processed=511))),
        (15.10, dict(content='', tokens=[42], stop=False)),
        (15.20, dict(content='Hello', tokens=[43], stop=False)),
        (16.00, dict(content='', stop=True, timings=dict(prompt_n=511, prompt_ms=5100,
                    prompt_per_second=100, predicted_n=2, predicted_per_second=2))),
    ]
    def post(body, consume):
        def chunks():
            for arrival, event in events:
                clock[0] = arrival
                yield ('data: ' + json.dumps(event) + '\n').encode()
        return consume(chunks())
    result = lab_v4_fast.request(SimpleNamespace(post=post), 'prompt', 2, benchmark=True, retain_tokens=True)
    assert result['generated_token_ids'] == [42, 43]
    assert result['client_ttft_ms'] == 5200
    assert result['request_total_ms'] == 6000
    assert [a['elapsed_ms'] for a in result['stream_arrivals'] if a['generated_content']] == [5200]
    assert result['text_head'] == 'Hello'


def test_p_derived_ttft_uses_first_progress_clock_and_first_sample_timestamp():
    from scripts.factory.r8_derive_p_ttft import derive
    raw = dict(arm='P', request='p512', state='warm', repeat=1, prompt_tokens=511, client_ttft_ms=40,
               prompt_ms=90316.8, request_total_ms=115301, quiet={'status': 'accepted'},
               prompt_progress=[dict(processed=0, time_ms=19), dict(processed=511, time_ms=90312)])
    assert derive(raw)['derived_ttft_ms'] == 90337.8
    assert raw['client_ttft_ms'] == 40
