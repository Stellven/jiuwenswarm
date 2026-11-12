"""Opt-in Nsight Systems tracing in the lab loop: summary parsing and Manager validation."""
from pathlib import Path

import pytest

from jiuwenswarm.factory import nsys_summary

KERN = '''Time (%),Total Time (ns),Instances,Avg (ns),Med (ns),Min (ns),Max (ns),StdDev (ns),Name
59.0,691287617,737,937975.1,490688.0,68832,28505984,3085233.8,"void mul_mat_vec_q<(ggml_type)8, (int)1>(const void *, const void *)"
41.0,480000000,10,1.0,1.0,1,1,0.0,"void flash_attn(float *)"
'''
OSRT = '''Time (%),Total Time (ns),Num Calls,Avg (ns),Med (ns),Min (ns),Max (ns),StdDev (ns),Name
60.0,600000000,100,1,1,1,1,0,pread
40.0,400000000,50,1,1,1,1,0,futex
'''


def test_summary_parses_exports(tmp_path):
    (tmp_path / 'nsys.nsys-rep').write_bytes(b'x' * 10)
    (tmp_path / 'nsys_cuda_gpu_kern_sum.csv').write_text(KERN)
    (tmp_path / 'nsys_osrt_sum.csv').write_text(OSRT)
    out = nsys_summary.summarize(tmp_path)
    assert out['traced'] is True
    assert out['kernels']['total_ms'] == pytest.approx(1171.288, rel=1e-4)
    assert out['kernels']['top'][0]['name'].startswith('mul_mat_vec_q<')
    assert out['kernels']['top'][0]['count'] == 737
    assert out['os_runtime']['top'][0] == dict(name='pread', percent=60.0, total_ms=600.0, count=100)
    assert sorted(out['missing']) == ['nsys_cuda_api_sum.csv', 'nsys_cuda_gpu_mem_time_sum.csv']


def test_no_report_means_no_summary(tmp_path):
    assert nsys_summary.summarize(tmp_path) is None


def test_manager_rejects_unknown_profile(tmp_path, monkeypatch):
    from jiuwenswarm.factory import manager as m
    mgr = m.Manager.__new__(m.Manager)
    monkeypatch.setattr(mgr, '_admission', lambda *a: {}, raising=False)
    monkeypatch.setattr(m.contracts, 'load', lambda cid: {'workload': {'env': {}, 'argv': []}})
    with pytest.raises(ValueError, match='profile must be nsys'):
        mgr.submit_run('t', 'a', 'c', {'env': {}, 'profile': 'ncu'}, 'k')
