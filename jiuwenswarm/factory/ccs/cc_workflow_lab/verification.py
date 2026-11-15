"""CPU invariants and adversarial inputs; independent expected arithmetic."""
import math
from workflow import analyze_receipts, benchmark_fixture, design_workflow, fixture, run_batch

def reject(fn, value):
    try:
        fn(value)
    except (ValueError, TypeError, KeyError):
        return
    raise AssertionError('invalid input accepted')

def verify():
    row = {'package': 'p', 'call': 'a', 'elapsed_s': 1., 'state': 'succeeded', 'completeness': 'complete'}
    rows = [row, {**row, 'call': 'b', 'elapsed_s': 3., 'state': 'failed'}]
    observed = analyze_receipts({'receipts': rows})
    assert observed['packages']['p'] == {'calls': 2, 'failures': 1, 'median_s': 2., 'total_s': 4.}
    real = analyze_receipts(fixture())
    assert real['call_count'] == 24 and len(real['packages']) == 7
    for bad in [float('nan'), float('inf'), -1, True, '0']:
        reject(analyze_receipts, {'receipts': [{**row, 'elapsed_s': bad}]})
    reject(analyze_receipts, {'receipts': [row, row]})
    reject(analyze_receipts, {'receipts': [row]*129})
    for op in ['run_batch', 'exec', 'factory.run', 'os.system']:
        reject(run_batch, {'jobs': [{'operation': op, 'spec': {}}]})
    reject(run_batch, {'jobs': [{'operation': 'analyze_receipts', 'spec': {'receipts': rows}, 'grants': ['network']} ]})
    for n in [0, 33, True, float('inf')]:
        reject(benchmark_fixture, {'repeats': n})
    job = {'operation': 'analyze_receipts', 'spec': {'receipts': rows}}
    assert run_batch({'jobs': [job, job]})['results'] == [{'operation': 'analyze_receipts', 'result': observed}]*2
    costs = design_workflow({'operation_count': 4, 'prepare_s': 1, 'invoke_s': 2, 'analysis_s': 3})
    assert [costs[k]['estimated_s'] for k in ['separate', 'reuse_release', 'cohesive_batch']] == [15, 12, 6]
    result = benchmark_fixture({'repeats': 2})
    assert len(result['raw_s']) == 2 and result['python_traced_peak_bytes'] > 0
    return {'passed': True, 'cpu_only': True, 'fixture_calls': real['call_count']}

if __name__ == '__main__':
    print(verify())
