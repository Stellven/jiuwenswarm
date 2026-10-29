"""Read completed Spark receipts; export small, credential-free report inputs.

No inference, app mutation, reviewer upload, or raw native-packet export.
Run locally with --ssh to execute this same collector over the existing SSH trust.
"""
import argparse
import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess

BASE = Path('/home/user2/ai4r-data/benchmarks')
COHORTS = [
    ('qwen', 'Fixed Qwen', 'local-routing-v1/results/campaign-001', 'fixed'),
    ('e4b', 'Historical E4B router', 'local-routing-v1/results/campaign-001', 'routed'),
    ('chatgpt', 'All ChatGPT', 'chatgpt-baseline-002', None),
    ('v3', 'Hybrid v3', 'hybrid-routing-002', None),
    ('v4', 'Hybrid v4', 'hybrid-riskbands-001', None),
    ('v5', 'Hybrid v5 (current)', 'hybrid-operations-001', None),
]


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def exact(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and actual.keys() == expected.keys() and all(
            exact(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            exact(a, b) for a, b in zip(actual, expected))
    if type(expected) in (int, float):
        return type(actual) in (int, float) and math.isfinite(actual) and actual == expected
    return type(actual) is type(expected) and actual == expected


def check_native(evidence, expected_prompt):
    """Validate packet hashes and actual dispatch/resolved-model/completion evidence."""
    packets = []
    for event in evidence['events']:
        raw = base64.b64decode(event['raw_base64'], validate=True)
        assert sha(raw) == event['record']['raw_ref']['sha256']
        assert sha(canonical(event['record'])) == event['ref']['sha256']
        packet = json.loads(raw)
        method = event['record'].get('method', '')
        assert not any(word in method.lower() for word in ('login', 'account', 'auth'))
        packets.append((event['record']['direction'], method, packet))
    outgoing = [p['params'] for d, m, p in packets if d == 'out' and m == 'turn/start']
    threads = [p['result'] for d, m, p in packets if d == 'in' and m == 'thread/start' and 'result' in p]
    terminal = [p['params']['turn'] for d, m, p in packets if m == 'turn/completed']
    assert len(outgoing) == 1 and len(threads) == 1 and len(terminal) == 1
    text = '\n'.join(part['text'] for part in outgoing[0]['input'] if part['type'] == 'text')
    assert sha(text.encode()) == expected_prompt
    assert threads[0]['model'] == 'gpt-6.1-sol'
    assert threads[0].get('reasoningEffort', threads[0]['thread'].get('reasoning_effort',
        threads[0]['thread'].get('reasoningEffort'))) == 'medium'
    assert terminal[0]['status'] == 'completed'
    return {'packet_hashes_verified': len(packets), 'prompt_sha256_verified': True,
            'resolved_model': threads[0]['model'], 'reasoning_effort': 'medium',
            'terminal': 'completed', 'trace_ref': evidence.get('trace_ref')}


def collect():
    source = BASE/'local-routing-v1/results/campaign-001'
    plan_raw = (source/'plan.json').read_bytes()
    source_plan = json.loads(plan_raw)
    gold_raw = (BASE/'local-routing-v1/results/campaign-001-reviewer/mr01-quality.json').read_bytes()
    assert sha(gold_raw) == source_plan['reviewer_pins']['mr01-quality']['sha256']
    gold = json.loads(gold_raw)['variants']
    observations, cohorts = [], []
    for ident, label, rel, phase in COHORTS:
        folder = BASE/rel
        plan_bytes = (folder/'plan.json').read_bytes()
        plan = json.loads(plan_bytes)
        if phase is None:
            assert sha(plan_raw) == plan['source_plan_sha256']
            assert sha(plan_bytes) == json.loads((folder/'plan-pin.json').read_text())['sha256']
            jobs = {(j['variant_id'], j['repeat']): j for j in plan['jobs']}
            files = sorted(folder.glob('*/result.json'))
        else:
            jobs = {}
            files = sorted(folder.glob('runs/*/result.json'))
        rows = []
        for file in files:
            raw = file.read_bytes()
            result = json.loads(raw)
            if phase is not None:
                if result['case_id'] != 'mr01-quality' or result['phase'] != phase:
                    continue
                variant, repeat = result['variant_id'], result['repeat']
            else:
                variant, repeat_text = file.parent.name.rsplit('-r', 1)
                repeat = int(repeat_text)
                assert result['prompt_sha256'] == jobs[(variant, repeat)]['prompt_sha256']
            text = result.get('text') if ident == 'chatgpt' else (result.get('worker') or {}).get('text', '')
            try:
                correct = exact(json.loads(text), gold[variant]['answer'])
            except (ValueError, TypeError):
                correct = False
            roles = defaultdict(lambda: {'calls': 0, 'input_tokens': 0, 'output_tokens': 0})
            if ident == 'chatgpt':
                usage = result['usage']
                roles['worker'] = {'calls': 1, 'input_tokens': usage['input_tokens'], 'output_tokens': usage['output_tokens']}
                choice = 'subscription:gpt-6.1-sol'
                native = [check_native(result['native_evidence'], result['prompt_sha256'])]
            else:
                for call in result['model_calls']:
                    record = call['record']
                    assert sha(canonical(record)) == call['ref']['sha256']
                    role = roles[record['call_function']]
                    role['calls'] += 1
                    role['input_tokens'] += record['usage']['input_tokens']
                    role['output_tokens'] += record['usage']['output_tokens']
                    assert record['outcome'] == 'completed'
                decisions = [d['record'] for d in result['decisions'] if d['record']['subnode_id'] == 'worker']
                assert len(decisions) == 1
                choice = decisions[0]['selected_candidate_id']
                native = [check_native(n, result['prompt_sha256']) for n in result.get('native_evidence', [])]
                for record in result.get('records', []):
                    assert sha(canonical(record['record'])) == record['ref']['sha256']
                assert not result.get('unresolved_claims')
            row = {'cohort': ident, 'variant': variant, 'repeat': repeat, 'correct': correct,
                   'gate': result.get('gate'), 'selected': choice, 'elapsed_s': result['elapsed_s'],
                   'roles': dict(roles), 'worker_output': text,
                   'verifier_output': (result.get('verifier') or {}).get('text'),
                   'native_proofs': native, 'source_path': str(file), 'source_sha256': sha(raw)}
            rows.append(row)
        assert len(rows) == 24 and len({(r['variant'], r['repeat']) for r in rows}) == 24
        aggregate_roles = defaultdict(lambda: {'calls': 0, 'input_tokens': 0, 'output_tokens': 0})
        for row in rows:
            for role, values in row['roles'].items():
                for key, value in values.items():
                    aggregate_roles[role][key] += value
        cohort = {'id': ident, 'label': label, 'source_directory': str(folder), 'phase': phase,
                  'n': len(rows), 'correct': sum(r['correct'] for r in rows),
                  'gated_correct': None if ident == 'chatgpt' else sum(r['correct'] and r['gate'] == 'advance' for r in rows),
                  'gates': dict(Counter(r['gate'] for r in rows if r['gate'])),
                  'choices': dict(Counter(r['selected'] for r in rows)), 'roles': dict(aggregate_roles),
                  'elapsed_s': sum(r['elapsed_s'] for r in rows),
                  'median_s': statistics.median(r['elapsed_s'] for r in rows),
                  'native_proofs': sum(len(r['native_proofs']) for r in rows),
                  'plan_sha256': sha(plan_bytes), 'controller_sha256': plan.get('controller_sha256'),
                  'launched': json.loads((folder/'launched.json').read_text()),
                  'monetary_cost': None,
                  'domains': {v: sum(r['correct'] for r in rows if r['variant'] == v) for v in sorted(gold)}}
        cohort['total_tokens'] = sum(v['input_tokens']+v['output_tokens'] for v in aggregate_roles.values())
        if (folder/'assessment.json').exists():
            assessment = json.loads((folder/'assessment.json').read_text())
            assert cohort['correct'] == assessment['exact_correct']
            assert cohort['gated_correct'] == assessment['gated_correct']
            assert cohort['total_tokens'] == assessment['total_tokens']
        cohorts.append(cohort)
        observations.extend(rows)
    return {'schema': 'ai4r-router-report-inputs:1', 'collected_at': datetime.now(timezone.utc).isoformat(),
            'host': platform.node(), 'platform': platform.platform(),
            'source_plan_sha256': sha(plan_raw), 'reviewer_sha256': sha(gold_raw),
            'reviewer_answers_exported': False, 'cohorts': cohorts, 'observations': observations,
            'scope': 'Public development MR01 component comparison; eight fixtures, three repeats per fixture; not full DAG acceptance.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ssh')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.ssh:
        if not args.output:
            parser.error('--output is required with --ssh')
        command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=yes',
                   '-o', 'HostKeyAlias=100.105.127.48', '-o', 'UserKnownHostsFile=D:/ai4r-cache/ssh/known_hosts',
                   args.ssh, 'python3', '-']
        response = subprocess.run(command, input=Path(__file__).read_bytes(), capture_output=True, timeout=60)
        if response.returncode:
            raise RuntimeError(response.stderr.decode('utf-8', errors='replace'))
        data = json.loads(response.stdout)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, indent=2, ensure_ascii=True)+'\n', encoding='utf-8')
        print(json.dumps({'output': str(args.output), 'observations': len(data['observations']),
                          'cohorts': [{k: c[k] for k in ('id', 'correct', 'gated_correct', 'total_tokens', 'elapsed_s')} for c in data['cohorts']]}))
    else:
        print(json.dumps(collect(), ensure_ascii=True))
