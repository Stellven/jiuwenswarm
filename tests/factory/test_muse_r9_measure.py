"""Model-free regression checks for the R9 one-load evidence path."""
from types import SimpleNamespace

import pytest

from jiuwenswarm.factory import muse_r9_measure as measure, muse_r9_runtime as runtime
from jiuwenswarm.factory.store import ScopeDenied
from scripts.factory import r8_bench_score, r8_derive_p_ttft, r9_prefix_check


def log_task(task_id, count, initial, *, stop=True):
    prefix = f'1.23.456 I slot operator(): id  0 | task {task_id} | '
    lines = [
        'processing task, is_child = 0',
        f'new prompt, n_ctx_slot = 8192, n_keep = 0, task.n_tokens = {count}',
        f'cached n_tokens = {initial}, memory_seq_rm [{initial}, end)',
        f'cached n_tokens = {count}, memory_seq_rm [{count}, end)',
    ]
    if stop:
        lines.append(f'stop processing: n_tokens = {count + 31}, truncated = 0')
    return ''.join(prefix + line + '\n' for line in lines).encode()


def test_reuse_uses_initial_log_count_scoped_to_task():
    raw = log_task(11, 2081, 0) + log_task(46, 2080, 2045)
    first, followup = measure.first_cached_tasks(raw)
    assert (first['cached_tokens'], followup['cached_tokens']) == (0, 2045)
    assert (first['task_id'], followup['task_id']) == (11, 46)
    assert followup['prompt_tokens'] - followup['cached_tokens'] == 35


def test_derived_ttft_preserves_shared_clock_with_reused_prompt():
    result = r8_derive_p_ttft.derive(dict(
        arm='AQBC', request='p2048', state='follow-up', repeat=0, prompt_tokens=35,
        prompt_ms=22804.0, request_total_ms=94100.0, client_ttft_ms=22844.6,
        prompt_progress=[dict(processed=2045, cache=2045, time_ms=0),
                         dict(processed=2080, cache=2045, time_ms=22804)],
        stream_arrivals=[dict(elapsed_ms=13.7, progress=True)], quiet={'status': 'accepted'}))
    assert result['derived_ttft_ms'] == 22817.7
    assert result['direct_client_ttft_ms'] == 22844.6


def test_measurement_refuses_an_ungranted_node_before_accessing_delivery():
    host = SimpleNamespace(get_task=lambda _: dict(contract_id=measure.TASK, resources={
        'memory_cap': '96G', 'device_budget_mib': 110000, 'need_available_gib': 100}))
    with pytest.raises(ScopeDenied, match='measure_engine node'):
        measure.admit(host, measure.TASK, {'request_id': 'fake'}, 'deliver_to_lab')
    with pytest.raises(ScopeDenied, match='host grant'):
        measure.admit(host, measure.TASK, {'request_id': 'fake'}, 'measure_engine')


def test_speed_and_followup_controls_share_clocks_and_never_reuse_unrelated_state(tmp_path, monkeypatch):
    server_log = tmp_path / 'server.log'
    server_log.touch()
    prompts = {name: f'Rendered notebook {name}<|eot|><|start|>assistant' for name in measure.PROMPTS}
    sizes = dict(p512=511, p2048=2047)
    followups = {text: (name, sizes[name] + 35)
                 for name, prompt in prompts.items() for text in r9_prefix_check.questions(prompt)}
    by_prompt = {prompt: (name, sizes[name]) for name, prompt in prompts.items()} | followups
    proposal = dict(speed_prompt_pins={
        name: dict(verified_server_tokens=sizes[name], sha256=measure.paired.sha(prompt))
        for name, prompt in prompts.items()})
    requests = []
    evictions = []
    server = SimpleNamespace(
        log=server_log, run=SimpleNamespace(log=lambda *_: None),
        post=lambda body, **_: {'tokens': list(range(by_prompt[body['content']][1]))})

    def fake_request(server, prompt, n_predict, *, benchmark, cache_prompt, retain_output):
        assert benchmark and n_predict == 32 and retain_output
        name, tokens = by_prompt[prompt]
        requests.append((prompt, cache_prompt))
        cached = sizes[name] - 2 if cache_prompt else 0
        with server.log.open('ab') as handle:
            handle.write(log_task(len(requests), tokens, cached))
        output = ' to=self<|message|>We need to read the field notebook and identify its recurring words.'
        ttft = 40 if cache_prompt else 100
        return dict(
            prompt_tokens=tokens - cached, prompt_ms=ttft - 10, client_ttft_ms=ttft,
            generated_tokens=32, request_total_ms=ttft + 100, decode_tokens_per_second=1.2,
            output_sha256=measure.paired.sha(output), output_text=output,
            ttft_method='client arrival of first non-empty generated content',
            prompt_progress=[dict(total=tokens, cache=cached, processed=cached, time_ms=0),
                             dict(total=tokens, cache=cached, processed=tokens, time_ms=ttft - 10)],
            stream_arrivals=[dict(elapsed_ms=10, progress=True, generated_content=False, stop=False),
                             dict(elapsed_ms=ttft, progress=False, generated_content=True, stop=False),
                             dict(elapsed_ms=ttft + 100, progress=False, generated_content=False, stop=True)])

    monkeypatch.setattr(measure.lab, 'request', fake_request)
    monkeypatch.setattr(measure.lab, 'evict', evictions.append)
    monkeypatch.setattr(measure, 'quiet_request',
                        lambda monitor, call: (call(), dict(status='accepted', reasons=[], samples=[]), None))
    monkeypatch.setattr(runtime.quiet, 'evidence_issues', lambda *_: [])
    limits = runtime.quiet.policy(runtime.quiet.EMPTY)
    stage = dict(launch_config=dict(request=dict(cache_prompt=True)), image_id='example',
                 pack=dict(first_shard='pinned.gguf', manifest_sha256='example'))

    speed = measure.run_speed(server, SimpleNamespace(limits=limits), tmp_path, proposal, prompts, stage, [])
    raw_log = server_log.read_bytes()
    indexed, policy, last = runtime._speed_rows(
        speed, measure.read(tmp_path / 'ttft.json'), raw_log, proposal, prompts)

    assert len(requests) == 20
    assert evictions == ['pinned.gguf'] * 4
    assert last == len(raw_log)
    assert [enabled for _, enabled in requests].count(True) == 2
    assert all(row['within_tolerance'] for row in runtime._standard_comparison(indexed, policy))
    followup = runtime._followup_comparison(indexed, proposal, policy)
    assert all(row['lower_ttft'] and row['meaningful_reuse'] for row in followup)
    assert [row['candidate']['derived_ttft_ms'] for row in followup] == [40, 40]
    assert [row['control']['derived_ttft_ms'] for row in followup] == [100, 100]

    raw_log = raw_log.replace(b'cached n_tokens = 509, memory_seq_rm [509, end)', b'cached n_tokens = 510, memory_seq_rm [510, end)')
    with pytest.raises(ValueError, match='slot task'):
        runtime._speed_rows(speed, measure.read(tmp_path / 'ttft.json'), raw_log, proposal, prompts)


def test_single_slot_score_keeps_exact_distribution_and_rejects_duplicate_reply_indices():
    question = dict(id='one', prompt='A multiple choice prompt', answer='A')
    top = [{'token': ' A' if idx == 0 else f'token{idx}', 'logprob': -idx - 0.1} for idx in range(20)]
    response = dict(index=0, id_slot=0, stop=True, truncated=False, tokens_evaluated=29, tokens_predicted=1,
                    completion_probabilities=[dict(top_logprobs=top)])
    posts = []

    def post(body):
        posts.append(body)
        return response

    result = r8_bench_score._scores(SimpleNamespace(post=post), [question], retain_distribution=True)
    assert posts == [dict(prompt=[question['prompt']], **r8_bench_score.REQUEST)]
    assert result['one']['correct'] is True
    assert result['one']['top_logprobs'][0] == [' A', -0.1]
    with pytest.raises(ValueError, match='duplicate prompt indices'):
        r8_bench_score._response_rows([response, response], [question, dict(question, id='two')])


def test_incomplete_measurement_refuses_release():
    result = runtime.verify_runtime_stage(dict(format=measure.FORMAT, status='stopped'))
    assert result['decision'] == 'refused'
    assert result['done'] is False
    assert result['checks'][0]['status'] == 'fail'
