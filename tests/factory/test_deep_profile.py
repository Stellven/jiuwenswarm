"""Bounded parsers exercise raw evidence, never GPU execution."""
import pytest

from jiuwenswarm.factory import deep_profile


def test_native_tables_rank_stages_without_double_counting_coarse_totals():
    stderr = '''ds4 prompt GPU time, 1200 tokens: attention 10 ms, routing + shared expert 20 ms, experts 70 ms (with the waits for streamed ones), between layers 0 ms
ds4 prof  between layers                        0.0 ms 0.0%
ds4 prof  attn rest (q_b, wo_a/b, hc_post)       10.0 ms 10.0%
ds4 prof  shared expert                        20.0 ms 20.0%
ds4 prof  experts (incl waits)                 70.0 ms 70.0%
ds4 prof  expert kernels total 70.0 ms
ds4 prof  between layers                        0.0 ms 0.0%
ds4 prof  experts (incl waits)                100.0 ms 100.0%
'''
    result = deep_profile.analyze({'stderr': stderr})
    native = result['native']
    assert native['tables'] == 2
    assert native['phase'] == 'prefill'
    assert native['candidate_bottleneck'] == 'experts (incl waits)'
    assert sum(stage['total_ms'] for stage in native['stages']) == 200
    assert result['expert_prediction']['recall_at_k'] is None
    assert result['scoring_eligible'] is False


def test_profile_failure_does_not_become_bottleneck_claim():
    out = deep_profile.native_stages('ds4 prof between layers 10.0 ms 100.0%\nds4: profiling disabled: cudaEventRecord failed\n')
    assert out['status'] == 'invalid'
    assert out['candidate_bottleneck'] is None


def test_nsight_sorts_by_time_and_keeps_overlapping_families_separate():
    csv = 'Total Time (ns),Instances,Name\n1000000,2,small\n9000000,5,large\n'
    result = deep_profile.analyze({'kernels': csv, 'cuda_api': csv})
    assert result['nsight']['kernels']['top'][0]['name'] == 'large'
    assert result['nsight']['kernels']['total_ms'] == 10
    assert 'total_ms' not in result
    assert result['native']['status'] == 'not_measured'


@pytest.mark.parametrize('text', ['Total Time (ns),Name\nnan,kernel\n',
    'Total Time (ns),Name\n-1,kernel\n', 'Total Time (ns),Instances,Name\n1,1.5,kernel\n',
    'Other,Name\n1,kernel\n'])
def test_malformed_csv_rejected(text):
    with pytest.raises(ValueError):
        deep_profile.nsight_csv(text)


def test_oversize_artifact_and_report_rejected():
    with pytest.raises(ValueError, match='8 MiB'):
        deep_profile.native_stages('x' * (deep_profile.MAX_BYTES + 1))
    with pytest.raises(ValueError, match='10000 rows'):
        deep_profile.nsight_csv('Total Time (ns),Name\n' + '1,kernel\n' * 10001)


def test_plan_has_no_execution_and_only_fixed_observer(monkeypatch):
    monkeypatch.setattr(deep_profile.shutil, 'which', lambda name: '/tools/'+name)
    result = deep_profile.plan()
    assert result['run_config'] == {'profile':'strata-native'}
    assert result['observer_environment'] == {'DS4_PROF':'1'}
    assert result['tools']['ncu']['execution_tested'] is False


def test_dispatch_uses_scoped_artifact_reads_and_publishes_provenance(store):
    artifact = store.put_artifact('t', 'native:stderr', b'ds4 prof between layers 4.0 ms 100.0%\n', 'text/plain', None)
    result = deep_profile.dispatch(store.scoped('t'), 't', 'analyze', {'artifacts':{'stderr':artifact['artifact_id']}})
    assert result['analysis']['native']['tables'] == 1
    assert result['evidence']['source_artifacts'] == ['native:stderr']
    store.create_task(dict(task_id='other', objective='isolation'))
    store.put_artifact('other', 'private', b'secret', 'text/plain', None)
    from jiuwenswarm.factory.store import NotFound
    with pytest.raises(NotFound):
        deep_profile.dispatch(store.scoped('t'), 't', 'analyze', {'artifacts':{'stderr':'private'}})


def test_partial_native_table_does_not_name_a_measured_bottleneck():
    from jiuwenswarm.factory.deep_profile import native_stages
    result = native_stages('ds4 prof expert work 12.0 ms 50.0%\n')
    assert result['status'] == 'not_measured'
    assert result['candidate_bottleneck'] is None


STREAM = ('ds4 prompt stream, CUDA0: 129 tokens in 2790 ms; 1550 experts streamed: '
          '1550 from the files (13.4 GB, 4.79 GB/s: 3.2 GB from the disk unbuffered, '
          '10.1 GB through the page cache), 0 from RAM (0.0 GB); 0 likely ones queued early, '
          '0 of them unpicked; the compute waited 459 ms for reads')
STREAM_DEBUG = '; io threads busy 3546 ms, copy_ahead staging 0 ms, DMA issues 0 ms, slot waits 0 ms'


def test_ordinary_stream_counters_need_no_profile_and_keep_overlap_separate():
    result = deep_profile.analyze({'stderr': STREAM + STREAM_DEBUG})
    assert result['native']['status'] == 'not_measured'
    stream = result['ordinary_stream']
    assert stream['status'] == 'measured'
    row = stream['records'][0]
    assert row['prompt_elapsed_ms'] == 2790
    assert row['io_worker_busy_ms'] == 3546  # legitimate overlap, not a 6336-ms prompt
    assert row['compute_read_wait_ms'] == 459
    assert row['read_wait_to_prompt_elapsed_ratio'] == pytest.approx(459 / 2790)
    assert row['reported_file_payload_gb_per_prompt_second'] == 4.79
    assert 'total_ms' not in stream and 'disk_bandwidth' not in row
    assert result['expert_prediction']['recall_at_k'] is None
    assert result['expert_prediction']['ready_at_demand_ratio'] is None
    assert result['expert_prediction']['wasted_bytes'] is None


def test_ordinary_stream_optional_debug_layer_cache_and_multiple_devices():
    cached = STREAM.replace('1550 experts streamed', '1553 experts streamed').replace(
        '(0.0 GB);', '(0.0 GB), 3 again from the layer cache (layer-major, 2 chunks, 1.5 GB of RAM);')
    out = deep_profile.stream_counters(cached + '\n' + STREAM.replace('CUDA0', 'CUDA1'))
    assert [row['device'] for row in out['records']] == [0, 1]
    assert out['records'][0]['layer_cache_experts'] == 3
    assert out['records'][0]['layer_cache_chunks'] == 2
    assert out['records'][0]['layer_cache_ram_gb'] == 1.5
    assert out['records'][0]['io_worker_busy_ms'] is None
    assert out['records'][1]['layer_cache_experts'] is None
    assert 'prompt_elapsed_ms' not in out  # no summed multi-device walltime


def test_ordinary_stream_format_drift_is_visible_and_missing_remains_unknown():
    out = deep_profile.stream_counters(STREAM + '\nds4 prompt stream, future format\n')
    assert out['status'] == 'partial' and out['unparsed_rows'] == 1
    assert deep_profile.stream_counters('no stream counters')['status'] == 'not_measured'
    zero = deep_profile.stream_counters(STREAM.replace('in 2790 ms', 'in 0 ms'))
    assert zero['records'][0]['read_wait_to_prompt_elapsed_ratio'] is None


@pytest.mark.parametrize('bad', [STREAM.replace('in 2790 ms', 'in nan ms'),
    STREAM.replace('in 2790 ms', 'in -1 ms'),
    STREAM.replace('in 2790 ms', 'in 1e-300 ms').replace('waited 459 ms', 'waited 1e300 ms'),
    STREAM.replace('1550 experts streamed', '1551 experts streamed'),
    STREAM.replace('0 of them unpicked', '1 of them unpicked')])
def test_ordinary_stream_invalid_values_rejected(bad):
    with pytest.raises(ValueError):
        deep_profile.stream_counters(bad)


def test_ordinary_stream_row_bound():
    with pytest.raises(ValueError, match='10000 rows'):
        deep_profile.stream_counters((STREAM + '\n') * 10001)
