"""Summarize measured predictor disposition and ready-byte evidence."""
from collections import defaultdict
import hashlib
import re


MARKER = 'expert_demand_predictor:'
GATE = 'LLAMA_EXPERT_PREDICT'
FIELDS = ('requested', 'already_resident', 'issued', 'issued_bytes', 'useful_ready', 'useful_bytes',
          'miss', 'late', 'unused', 'pending')
OPTIONAL = ('opportunities', 'completed_transfers', 'completed_bytes', 'wasted_bytes', 'denied', 'duplicate', 'unknown', 'reused')
PHASES = ('prefill', 'decode')
OOM = ('oom', 'oom_kill', 'oom_group_kill')
CAP = {'memory.max': str(100 * 1024**3), 'memory.swap.max': '0', 'memory.oom.group': '1',
       'cpu.max': '800000 100000', 'sched_affinity': list(range(8))}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def reference(value):
    if not value['artifact_id'] or not re.fullmatch('[0-9a-f]{64}', value['sha256']):
        raise ValueError('Canonical output needs retained artifact IDs and SHA-256')
    return value


def counters(log):
    result = defaultdict(list)
    seen = set()
    for text in re.findall(r'expert_demand_predictor: native\s+([^\n]+)', log):
        pairs = [part.split('=', 1) for part in text.split()]
        if any(len(pair) != 2 for pair in pairs):
            raise ValueError('Native predictor row must have named counters')
        fields = dict(pairs)
        if len(fields) != len(pairs):
            raise ValueError('Duplicate native predictor counter')
        phase = fields.pop('phase')
        if 'request_id' in fields and 'request' in fields:
            raise ValueError('Duplicate native predictor request identity')
        request = fields.pop('request_id', None) if 'request_id' in fields else fields.pop('request', None)
        sequence, graph = fields.pop('sequence', None), fields.pop('graph', None)
        if 'success' in fields:
            completed = fields.pop('success')
            fields['completed_transfers'] = fields.pop('completed')
        else:
            completed = fields.pop('completed', None) if graph is not None else None
        identity = (phase, request, sequence, graph)
        if (phase not in PHASES or identity in seen or any(not x.isdecimal() for x in identity[1:] if x is not None) or
                (graph is not None and (request is None or sequence is None or completed not in ('0', '1')))):
            raise ValueError('Unknown phase or duplicate predictor outcome row')
        seen.add(identity)
        if set(FIELDS) - fields.keys() or any(not x.isdecimal() for x in fields.values()):
            raise ValueError('Observed native predictor counters are incomplete')
        row = {key: int(value) for key, value in fields.items()}
        if (row['already_resident'] + row['issued'] > row['requested'] or row['useful_ready'] > row['issued'] or
                row['useful_bytes'] > row['issued_bytes'] or row['late'] > row['issued'] or row['unused'] > row['issued'] or
                row['pending'] > row['issued'] or bool(row['issued']) != bool(row['issued_bytes']) or
                bool(row['useful_ready']) != bool(row['useful_bytes'])):
            raise ValueError('Observed predictor counters do not conserve admitted counts and bytes')
        if 'completed_transfers' in row and not row['useful_ready'] <= row['completed_transfers'] <= row['issued']:
            raise ValueError('Observed readiness exceeds completed or issued prefetches')
        result[phase].append(dict(request_id=request, sequence=sequence, graph=graph,
                                  graph_completed=None if completed is None else completed == '1', counts=row))
    phases = {}
    for phase in PHASES:
        rows = result[phase]
        if any(row['request_id'] is None for row in rows) and len(rows) != 1:
            raise ValueError('Scope and request totals cannot be added for the same predictor phase')
        totals = {key: sum(row['counts'][key] for row in rows) if all(key in row['counts'] for row in rows) else None
                  for key in (*FIELDS, *OPTIONAL)} if rows else None
        phases[phase] = dict(coverage='observed' if rows else 'unobserved', totals=totals, rows=rows,
                            failed_graph_rows=sum(row['graph_completed'] is False for row in rows))
    return phases


def summarize(packet):
    if packet['schema'] != 'spark-native-prefetch-evidence/1' or set(packet['arms']) != {'stock', 'off', 'on'}:
        raise ValueError('Use stock A+, candidate off and candidate on from the same admitted experiment')
    result = {}
    reference_match, parity, candidate_build = None, None, None
    for role in ('stock', 'off', 'on'):
        scope = packet['arms'][role]
        for key in ('start', 'stop', 'scope', 'log', 'probe'):
            reference(scope['references'][key])
        stop, start, kernel = (scope[k] for k in ('stop', 'start', 'scope'))
        logged = scope['stderr']
        if (digest(logged.encode()) != scope['references']['log']['sha256'] or
                stop['returncode'] or stop['reason'] or stop['scope_verified'] is not True or
                stop['min_mem_available_bytes'] < 8 * 1024**3 or
                any(int(stop['memory_events'].get(k, 0)) for k in OOM) or
                any(kernel['actual'].get(k) != value for k, value in CAP.items()) or
                any(start[k] != stop[k] for k in ('command', 'binary_sha256', 'unit', 'launch_environment'))):
            raise ValueError('Native predictor scope admission, clean shutdown or log digest failed')
        gates = {k: v for k, v in start['launch_environment'].items() if k.startswith('LLAMA_')}
        desired = {GATE: '1'} if role == 'on' else {}
        if gates != desired:
            raise ValueError('The native predictor gate is the only capsule treatment allowed in this experiment')
        matches = re.findall(r'CUDA0 MoE cache size = ([\d.]+) MiB for ([\d.]+) MiB of host experts, ([\d.]+)% of the misses on the CPU', logged)
        cmd = start['command']
        if (len(matches) != 1 or cmd[cmd.index('--moe-cache-mib') + 1] != '30720' or
                cmd[cmd.index('--moe-cache-cpu-share') + 1] != '0' or not 0 < float(matches[0][0]) <= 30720 or
                float(matches[0][2]) != 0):
            raise ValueError('Observed A+30 bank allocation or CPU miss setting is missing')
        shared = {k: v for k, v in start['launch_environment'].items() if k.startswith('GGML_')}
        matching = (cmd[1:], matches[0], shared)
        output = scope['probe']['greedy_hashes']
        if set(output) != {'512', '2048'} or any(len(pair) != 2 or not all(re.fullmatch('[0-9a-f]{64}', value) for value in pair)
                                                for pair in output.values()):
            raise ValueError('Expected fixed greedy output and reasoning hashes for both prompts')
        if reference_match is None:
            reference_match, parity = matching, output
        if matching != reference_match or output != parity:
            raise ValueError('Native predictor controls disagree on flags, allocation or greedy parity')
        if role == 'off':
            candidate_build = start['binary_sha256']
        elif role == 'on' and candidate_build != start['binary_sha256']:
            raise ValueError('Candidate gate on and off do not share an exact executable')
        inactive = re.findall(r'expert_demand_predictor: inactive \(([^\n]+)\)', logged)
        phases = counters(logged)
        observed = any(row['coverage'] == 'observed' for row in phases.values())
        if role != 'on' and MARKER in logged:
            raise ValueError('Predictor emitted a marker in a control')
        issued = sum(row['totals']['issued'] for row in phases.values() if row['totals'])
        state = 'observed-issue' if issued else 'observed-no-issue' if observed else 'inactive' if inactive else 'unobserved'
        result[role] = dict(binary_sha256=start['binary_sha256'], status=state, reasons=inactive, phases=phases,
                            activation_marker='expert_demand_predictor: active ' in logged,
                            references=scope['references'])
    return dict(schema='spark-native-prefetch-readiness/1', kind='analysis', requested_mib=30720,
                actual_allocated_mib=float(reference_match[1][0]), arms=result, matched_greedy_hashes=parity,
                summary='Matched A+30 runtime controls distinguish native prefetch issue from useful demand-time readiness.',
                limitations='A requested or issued prefetch is not a ready hit. Missing native rows are unobserved. Late misses and unused issues retain their separately observed meanings. These functional scopes are not timing evidence.')
