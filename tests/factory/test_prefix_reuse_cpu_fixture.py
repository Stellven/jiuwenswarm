"""The fixture attributes cache reuse only to the request's first cache line."""

import pytest

from scripts.factory.prefix_reuse_cpu_fixture import read_request_cache


def log_slice(initial=0, *, task=41, prompt=786, finish=True):
    marker = f'0.01.230.002 I slot operator(): id  0 | task {task} | '
    lines = [
        'processing task, is_child = 0',
        f'new prompt, n_ctx_slot = 2048, n_keep = 0, task.n_tokens = {prompt}',
        f'cached n_tokens = {initial}, memory_seq_rm [{initial}, end)',
        'cached n_tokens = 768, memory_seq_rm [768, end)',
    ]
    if finish:
        lines.append('stop processing: n_tokens = 801, truncated = 0')
    return ''.join(marker + line + '\n' for line in lines).encode()


@pytest.mark.parametrize('cached', [0, 512, 770])
def test_reader_selects_first_cache_line(cached):
    observation = read_request_cache(log_slice(cached), 786)
    assert observation['cached_tokens'] == cached
    assert f'cached n_tokens = {cached},' in observation['cache_line']
    assert observation['task_id'] == 41


@pytest.mark.parametrize('raw', [log_slice(finish=False), log_slice(prompt=787), log_slice(initial=786),
                                 log_slice() + log_slice(task=42)])
def test_reader_refuses_unscoped_or_invalid_evidence(raw):
    with pytest.raises(ValueError):
        read_request_cache(raw, 786)


def test_portable_verifier_reports_equal_reuse_and_stock_checkpoint_default():
    from jiuwenswarm.factory.ccs.kv_reuse_lab.cpu_fixture import verify

    prefix = list(range(769))
    stock_startup = ('n_swa = 512\nCPU_Mapped model buffer size = 240 MiB\n'
                     'context checkpoints enabled, max = 32\n')
    configured_startup = stock_startup + 'using full-size SWA cache\n'
    row = dict(model_sha256='a' * 64, executable_sha256='b' * 64, cache_prompt=True,
               request_logs=[log_slice().decode(), log_slice(769, task=42).decode()])
    evidence = dict(model=dict(sha256='a' * 64, bytes=250_000_000, window_tokens=512),
                    executable_sha256='b' * 64,
                    request_tokens=[prefix + [900] * 17, prefix + [901] * 17],
                    configurations=dict(stock=dict(row, extra_args=[], startup_log=stock_startup),
                        configured=dict(row, extra_args=['--swa-full', '--ctx-checkpoints', '32'],
                                        startup_log=configured_startup)))
    result = verify(evidence)
    assert result['stage'] == 'factory' and result['cached_tokens_delta'] == 0
    assert [result['configurations'][name]['checkpoints_max'] for name in ('stock', 'configured')] == [32, 32]
    assert result['configurations']['stock']['full_swa'] is False
    assert result['configurations']['configured']['full_swa'] is True

    evidence['configurations']['configured']['executable_sha256'] = 'changed'
    with pytest.raises(ValueError, match='same pinned model and executable'):
        verify(evidence)
