"""Quick CPU behavior checks; no model, network or deployment calls."""
import copy
import json
from pathlib import Path
from components import assess_transfer, design_trial, analyze_abba


def rejected(fn, value):
    try:
        fn(value)
    except ValueError:
        return
    raise AssertionError('Invalid evidence accepted')


def verify():
    examples = {k: v['request'] for k, v in json.loads(Path(__file__).with_name('EXAMPLES.json').read_text()).items()}
    source = copy.deepcopy(examples['assess_transfer'])
    assert assess_transfer(source)['admission_granted'] is False
    source['requires']['disjoint_cpu_gpu_capacity'] = True
    assert 'unified_memory_capacity_cannot_be_counted_twice' in assess_transfer(source)['blockers']
    source['semantics'] = 'expert_skipping'
    assert 'expert_skipping_outside_exact_lane' in assess_transfer(source)['blockers']
    trial = copy.deepcopy(examples['design_trial'])
    assert design_trial(trial)['first_test'] == 'causal_trace_replay'
    trial['change']['another'] = 1
    rejected(design_trial, trial)
    abba = copy.deepcopy(examples['analyze_abba'])
    got = analyze_abba(abba)
    assert abs(got['combined_ratio'] - 1.0027646831596184) < 1e-12
    assert got['exact_outputs_equal'] is True
    # Independently hand-check warmup exclusion with asymmetric native phases.
    for cell in abba['cells']:
        for i, row in enumerate(cell['requests']):
            row['prefill_ms'] = 999999 if i == 0 else 100
            row['decode_ms'] = 999999 if i == 0 else (900 if cell['arm'] == 'A' else 400)
    assert analyze_abba(abba)['combined_ratio'] == 2
    bad = copy.deepcopy(abba)
    bad['cells'][1]['requests'][1]['input_sha256'] = 'b' * 64
    rejected(analyze_abba, bad)
    bad = copy.deepcopy(abba)
    bad['cells'][1]['requests'][1]['decode_ms'] = float('nan')
    rejected(analyze_abba, bad)
    for timing in (1e308, 1e-300):
        bad['cells'][1]['requests'][1]['decode_ms'] = timing
        rejected(analyze_abba, bad)
    abba['cells'][1]['requests'][1]['output_sha256'] = None
    assert analyze_abba(abba)['exact_outputs_equal'] is None
    return {'cpu_reference_checks': 'passed', 'gpu_executed': False, 'admission_granted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
