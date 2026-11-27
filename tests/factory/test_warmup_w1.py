"""Model-free checks for the one-load W1 protocol."""

from types import SimpleNamespace

import pytest

from scripts.factory import warmup_w1 as w1


def server_log(total=511, cached=0):
    return ''.join('1.23.456 I slot operator(): id  0 | task 24 | ' + text + '\n' for text in (
        'processing task, is_child = 0',
        f'new prompt, n_ctx_slot = 8192, n_keep = 0, task.n_tokens = {total}',
        f'cached n_tokens = {cached}, memory_seq_rm [{cached}, end)',
        f'cached n_tokens = {total}, memory_seq_rm [{total}, end)',
        f'stop processing: n_tokens = {total + 31}, truncated = 0',
    ))


def fake_probes(events):
    def residency(*_):
        events.append('residency')
        return {'status': 'measured', 'resident_bytes': (4 if 'evict' in events else 9) * 4096}

    def memory(_):
        events.append('memory')
        return {'scope': {'max_bytes': 96 * 2**30, 'swap_max_bytes': 0}}

    def counter(_):
        events.append('counter')
        return {'status': 'unavailable'}

    return SimpleNamespace(pack_residency=residency, server_memory=memory, counter_probe=counter,
                           counter_delta=lambda *_: {'status': 'unavailable'})


def fake_monitor():
    return SimpleNamespace(limits=w1.quiet.policy(w1.quiet.SHARED),
                           samples=[dict(phase='start', reasons=[]), dict(phase='end', reasons=[])],
                           wait=lambda *_: (0, False), mark=lambda *_: 1)


def fake_metrics():
    return dict(prompt_tokens=511, generated_tokens=32, client_ttft_ms=80025.0,
                prompt_ms=80000.0, decode_tokens_per_second=1.1, request_total_ms=110000.0,
                output_text='A coherent short response.',
                prompt_progress=[dict(processed=0, cache=0, time_ms=0), dict(processed=511, time_ms=80000)],
                stream_arrivals=[dict(elapsed_ms=10.0, progress=True),
                                 dict(elapsed_ms=80025.0, progress=False, generated_content=True)])


def test_approved_sequence():
    assert w1.schedule() == [
        ('D1', 'startup'), ('D2', 'new'), ('D3', 'new'), ('D4', 'new'), ('D5', 'new'), ('D6', 'new'),
        ('D6', 'repeat'), ('D6', 'repeat'), ('D6', 'repeat'), ('D6', 'repeat'), ('D6', 'after_page_evict'),
        ('E1', 'new'), ('E2', 'new'), ('E2', 'repeat'), ('E2', 'repeat'),
    ]


@pytest.mark.parametrize('cached', [0, 7])
def test_full_row_checkpoints_clocks_eviction_and_initial_reuse(tmp_path, monkeypatch, cached):
    events = []
    log = tmp_path / 'server.log'
    log.touch()
    event = SimpleNamespace(log=log, run=SimpleNamespace(log=lambda *_: None))
    doc = w1.Document('D6', 512, 'paper note', tuple(range(511)))
    pack = {'manifest': str(tmp_path / 'manifest.json'), 'manifest_sha256': 'a', 'first_shard': 'pinned.gguf'}

    def request(server, prompt, n_predict, **kw):
        assert prompt == doc.text and n_predict == 32
        assert kw == dict(benchmark=True, cache_prompt=False, retain_output=True)
        assert w1.bench.read(tmp_path / '11.json')['status'] == 'measuring'
        events.append('request')
        log.write_text(server_log(cached=cached))
        return fake_metrics()

    monkeypatch.setattr(w1.lab, 'request', request)
    monkeypatch.setattr(w1.lab, 'evict', lambda path: events.append('evict'))
    if cached:
        with pytest.raises(ValueError, match='zero cached tokens'):
            w1.live_row(event, fake_monitor(), fake_probes(events), tmp_path, doc, 'after_page_evict', 11, pack)
        row = w1.bench.read(tmp_path / '11.json')
        assert row['status'] == 'stopped'
    else:
        row = w1.live_row(event, fake_monitor(), fake_probes(events), tmp_path, doc, 'after_page_evict', 11, pack)
        assert row['status'] == 'complete'
        assert row['derived_ttft_ms'] == 80010
        assert row['direct_client_ttft_ms'] == 80025
        assert row['server_request']['cached_tokens'] == 0
    assert row['page_cache_before_eviction']['resident_bytes'] == 9 * 4096
    assert row['page_cache_before']['resident_bytes'] == 4 * 4096
    assert events == ['residency', 'evict', 'residency', 'memory', 'counter', 'request', 'counter']


def test_live_tokenizer_compares_ids_without_a_completion():
    calls = []
    doc = w1.Document('D1', 512, 'rendered notebook', (1, 2, 3))

    def post(body, *, path, timeout):
        calls.append((body, path))
        return {'tokens': [1, 2, 3]}

    w1.verify_live_tokenizer(SimpleNamespace(post=post), {doc.name: doc})
    assert calls == [({'content': doc.text, 'add_special': True, 'parse_special': True}, '/tokenize')]
