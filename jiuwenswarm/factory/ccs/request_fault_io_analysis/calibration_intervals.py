"""Analyze genuinely observed decode intervals in a completed native tuner run."""
from collections import defaultdict
import json
import re

from fault_io import read_pinned, uint, window


PROGRESS = re.compile(r'\bslot\s+print_timing:\s+id\s+(\d+)\s+\| task\s+(\d+)\s+\| n_gen\s*=\s*(\d+), tg\s*=\s*(\d+(?:\.\d+)?)\s+t/s')
METRICS = ('cgroup_pgfault', 'cgroup_pgmajfault', 'cgroup_file_refault', 'cgroup_pages_scanned',
           'cgroup_pages_reclaimed', 'process_minflt', 'process_majflt', 'process_read_bytes', 'host_nvme_read_bytes')
LIMIT = (
    'Periodic snapshots of stochastic A+ calibration decode, outside first-token timing. '
    'Logged n_gen is an asynchronous progress marker and can lag the counter boundary. '
    'Process, cgroup and host-device counters have distinct scopes. '
    'Hardware prefill timing, tensor-page attribution, I/O critical path and causal cache benefit remain unmeasured.'
)


def process(sample):
    engines = [(pid, row['starttime_ticks']) for pid, row in sample['counters']['processes'].items()
               if row.get('comm') == 'llama-server' and uint(row.get('starttime_ticks'))]
    return engines[0] if len(engines) == 1 else None


def analyze(trace, log, hashes):
    progress = []
    matching = defaultdict(list)
    for line_number, line in enumerate(log.splitlines(), start=1):
        match = PROGRESS.search(line)
        if match is None:
            continue
        slot, task, count, rate = match.groups()
        matching[int(count), float(rate)].append(len(progress))
        progress.append((int(slot), int(task), line_number))
    samples = [json.loads(line) for line in trace.splitlines()]
    if len(samples) < 2 or any(row['schema'] != 'spark-tuner-decode-diagnostic/1' for row in samples):
        raise ValueError('Expected a periodic tuner diagnostic series')

    def identities(sample):
        key = sample['last_logged_n_gen'], sample['reported_tok_s']
        matches = matching[key]
        return matches[0] if len(matches) == 1 else None

    rows, excluded = [], []
    for i, (a, b) in enumerate(zip(samples[:-1], samples[1:], strict=True)):
        low, high = identities(a), identities(b)
        engine_a, engine_b = process(a), process(b)
        record = {
            'snapshot_start': i,
            'snapshot_end': i + 1,
            'utc_start': a['counters']['utc'],
            'utc_end': b['counters']['utc'],
            'n_gen_start': a['last_logged_n_gen'],
            'n_gen_end': b['last_logged_n_gen'],
        }
        if low is None or high is None:
            excluded.append(record | {'reason': 'missing_or_ambiguous_progress_log_match'})
            continue
        if low >= high or records_cross_requests(progress[low:high + 1]) or record['n_gen_end'] <= record['n_gen_start']:
            excluded.append(record | {'reason': 'no_advance_or_crosses_request_boundary'})
            continue
        if engine_a is None or engine_a != engine_b:
            excluded.append(record | {'reason': 'server_pid_identity_not_stable'})
            continue
        observed = window(a['counters'], b['counters'])
        metrics = {(row['source'], row['counter']): row['delta'] for row in observed['rows']
                   if row['source'].startswith('cgroup.memory.') or row['resource'] == f'{engine_a[0]} (llama-server)'}
        host_reads = [row['delta'] for row in observed['rows'] if row['source'] == 'host.diskstats' and row['counter'] == 'read_bytes']
        elapsed = observed['elapsed_s']
        tokens = record['n_gen_end'] - record['n_gen_start']
        if elapsed <= 0:
            raise ValueError('Eligible decode interval duration must be positive')
        measure = {
            'cgroup_pgfault': metrics.get(('cgroup.memory.stat', 'pgfault')),
            'cgroup_pgmajfault': metrics.get(('cgroup.memory.stat', 'pgmajfault')),
            'cgroup_file_refault': metrics.get(('cgroup.memory.stat', 'workingset_refault_file')),
            'cgroup_pages_scanned': metrics.get(('cgroup.memory.stat', 'pgscan')),
            'cgroup_pages_reclaimed': metrics.get(('cgroup.memory.stat', 'pgsteal')),
            'process_minflt': metrics.get(('process.stat', 'minflt')),
            'process_majflt': metrics.get(('process.stat', 'majflt')),
            'process_read_bytes': metrics.get(('process.io', 'read_bytes')),
            'host_nvme_read_bytes': host_reads[0] if len(host_reads) == 1 else None,
        }
        rows.append(record | {
            'slot_id': progress[low][0], 'task_id': progress[low][1],
            'log_lines': [progress[low][2], progress[high][2]],
            'server_pid': engine_a[0], 'server_starttime_ticks': engine_a[1],
            'elapsed_s': elapsed,
            'logged_token_delta': tokens, 'logged_tokens_per_second': tokens / elapsed,
            **measure,
            'process_read_bytes_per_logged_token': measure['process_read_bytes'] / tokens if measure['process_read_bytes'] is not None else None,
            'cgroup_io_stat_present': observed['source_presence']['cgroup.io.stat'],
        })
    if not rows:
        raise ValueError('No unambiguous intervals from an advancing decode request')
    by_task = defaultdict(list)
    for row in rows:
        by_task[row['task_id']].append(row)
    summaries = [
        {
            'task_id': task,
            'intervals': len(group),
            'elapsed_s': sum(row['elapsed_s'] for row in group),
            'logged_token_delta': sum(row['logged_token_delta'] for row in group),
            **{key: sum(row[key] for row in group) if all(row[key] is not None for row in group) else None for key in METRICS},
        }
        for task, group in sorted(by_task.items())
    ]
    return {
        'schema': 'calibration-fault-io-analysis/1',
        'kind': 'analysis',
        'title': 'A+ native-tuner decode faults and backing-store reads',
        'sha256': hashes, 'rows': rows, 'request_summaries': summaries, 'excluded_intervals': excluded,
        'ttft_s': None, 'limitations': LIMIT,
    }


def records_cross_requests(records):
    return len({(slot, task) for slot, task, _ in records}) != 1


def analyze_artifacts(artifacts):
    # Engine logs may include raw generated bytes alongside ASCII progress lines.
    return analyze(read_pinned(artifacts['trace']), read_pinned(artifacts['engine_log']).decode(errors='replace'),
                   {name: item['sha256'] for name, item in artifacts.items()})
