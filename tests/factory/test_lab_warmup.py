"""Exercise the target warm-up phase without a model or GPU."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from scripts.factory import lab_warmup, lab_v4_quiet
from scripts.factory.warmup_w1 import document_shell, fit_notebook

TEMPLATE = '<|start|>user<|message|>Read this notebook.\n\n' + 'river valley ' * 12 + '<|eot|><|start|>assistant'
MEASURED = [TEMPLATE, 'another measured document', 'independent scoring case']


def tokens(text):
    return tuple(int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], 'big') for word in text.split())


class FakeServer:
    def __init__(self, log, rates):
        self.log = log
        log.touch()
        self.messages = []
        self.completions = []
        self.rates = iter(rates)
        self.run = SimpleNamespace(log=self.messages.append)

    def post(self, body, *, path, timeout):
        assert path == '/tokenize'
        assert body['add_special'] is body['parse_special'] is True
        return {'tokens': list(tokens(body['content']))}

    def request(self, prompt, n_predict, *, benchmark, cache_prompt):
        assert benchmark is True and cache_prompt is False and n_predict == 32
        self.completions.append(prompt)
        index = len(self.completions)
        total = len(tokens(prompt))
        lines = [
            'processing task, is_child = 0',
            f'new prompt, n_ctx_slot = 8192, n_keep = 0, task.n_tokens = {total}',
            'cached n_tokens = 0, memory_seq_rm [0, end)',
            f'cached n_tokens = {total}, memory_seq_rm [{total}, end)',
            f'stop processing: n_tokens = {total + 31}, truncated = 0',
        ]
        with self.log.open('a') as log:
            log.writelines(f'1.23.456 I slot operator(): id 0 | task {index} | {line}\n' for line in lines)
        return dict(prompt_tokens=total, generated_tokens=32, client_ttft_ms=90025.0,
                    prompt_ms=90000.0, decode_tokens_per_second=next(self.rates), request_total_ms=120000.0,
                    prompt_progress=[dict(processed=0, cache=0, time_ms=0), dict(processed=total, time_ms=90000)],
                    stream_arrivals=[dict(elapsed_ms=10.0, progress=True),
                                     dict(elapsed_ms=90025.0, progress=False, generated_content=True)])


@pytest.fixture
def monitor():
    return SimpleNamespace(limits=lab_v4_quiet.policy(lab_v4_quiet.SHARED),
                           samples=[dict(phase='start', reasons=[]), dict(phase='end', reasons=[])],
                           wait=lambda *_: (0, False), mark=lambda *_: 1)


@pytest.mark.parametrize(('rates', 'count', 'reason', 'line'), [
    ([1.0, 1.05, 9.0], 2, 'stable', 'warm-up: 2 requests, stable at 1.05 tok/s'),
    ([0.8, 1.0, 1.2, 1.5, 1.8, 2.2], 6, 'cap_reached',
     'warm-up: 6 requests, stability not reached (last 2.20 tok/s)'),
])
def test_stops_at_first_stable_pair_or_six(tmp_path, monkeypatch, monitor, rates, count, reason, line):
    server = FakeServer(tmp_path / 'server.log', rates)
    monkeypatch.setattr(lab_warmup.lab, 'request', lambda server, *args, **kwargs: server.request(*args, **kwargs))
    report = lab_warmup.run(server, monitor, tmp_path, template=TEMPLATE, measured_prompts=MEASURED)
    assert len(server.completions) == len(report['requests']) == count
    assert len(set(server.completions)) == count
    assert set(server.completions).isdisjoint(MEASURED)
    assert report['stop_reason'] == reason
    assert server.messages == [report['summary']] == [line]
    raw = server.log.read_bytes()
    assert lab_warmup.validate(report, raw, len(raw), MEASURED) == line
    row = report['requests'][0]
    assert row['derived_ttft_ms'] == 90010.0 and row['direct_client_ttft_ms'] == 90025.0
    row['rendered_prompt_tokens'] += 1
    with pytest.raises(ValueError, match='timing or identity'):
        lab_warmup.validate(report, raw, len(raw), MEASURED)


def test_disjointness_is_enforced_before_sending(tmp_path, monkeypatch, monitor):
    server = FakeServer(tmp_path / 'server.log', [])
    head, tail = document_shell(TEMPLATE)
    duplicate, _ = fit_notebook(head, tail, lab_warmup.NOTEBOOKS[0], tokens, len(tokens(TEMPLATE)))

    def should_not_send(*args, **kwargs):
        raise AssertionError('A warm-up duplicate was sent')

    monkeypatch.setattr(lab_warmup.lab, 'request', should_not_send)
    with pytest.raises(ValueError, match='overlaps a measured or previous warm-up prompt'):
        lab_warmup.run(server, monitor, tmp_path, template=TEMPLATE, measured_prompts=MEASURED + [duplicate])
    assert server.completions == []
    receipt = json.loads((tmp_path / 'warmup.json').read_text())
    assert receipt['status'] == 'stopped' and receipt['stop_reason'] == 'request_or_evidence_error'
