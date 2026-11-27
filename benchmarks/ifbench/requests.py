"""Lossless completion observation and explicitly defined client throughput."""
import json
import threading
import time
import uuid
from pathlib import Path


def counts(usage, timings):
    usage, timings = usage or {}, timings or {}
    output = usage.get('completion_tokens')
    source = 'usage.completion_tokens'
    if output is None:
        output, source = timings.get('predicted_n'), 'timings.predicted_n'
    return (usage.get('prompt_tokens', timings.get('prompt_n')), output,
            source if output is not None else 'unavailable')


def rates(output, elapsed, first, last):
    """Stream events can contain multiple tokens: the decode rate is an estimate."""
    return {
        'e2e_output_tok_s': output / elapsed if output is not None and elapsed > 0 else None,
        'decode_tok_s_client_estimate': (output - 1) / (last - first)
        if output is not None and output > 1 and first is not None and last is not None and last > first else None,
        'decode_boundary': 'first to last nonempty text event; estimated, events are not tokens',
    }


class Capture:
    """One observer per HTTP request; no headers or credentials are persisted."""
    lock = threading.Lock()

    def __init__(self, path, endpoint, body):
        self.path = Path(path)
        self.row = {'schema_version': 1, 'request_id': uuid.uuid4().hex,
                    'endpoint': endpoint, 'request': body, 't_send_unix': time.time(),
                    't_send_monotonic': time.monotonic(), 'events': []}
        self.usage = self.timings = None
        self.text, self.reasoning = [], []
        self.finish_reason = None
        self.buffer = b''
        self.first = self.last = None
        self.done = False
        self.finished = False

    def observe(self, obj, streamed=True):
        self.usage = obj.get('usage') or self.usage
        self.timings = obj.get('timings') or self.timings
        for choice in obj.get('choices') or []:
            self.finish_reason = choice.get('finish_reason') or self.finish_reason
            delta = choice.get('delta') or choice.get('message') or {}
            text = choice.get('text') or delta.get('content') or ''
            reasoning = delta.get('reasoning_content') or delta.get('reasoning') or ''
            if text or reasoning:
                now = time.monotonic() - self.row['t_send_monotonic']
                if streamed:
                    self.first = now if self.first is None else self.first
                    self.last = now
                    self.row['events'].append({'offset_s': now, 'text': text, 'reasoning': reasoning})
                self.text.append(text)
                self.reasoning.append(reasoning)

    def feed(self, chunk):
        self.buffer += chunk
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            if line.startswith(b'data:'):
                data = line[5:].strip()
                if data == b'[DONE]':
                    self.done = True
                elif data:
                    self.observe(json.loads(data))

    def finish(self, status, error=None, nonstream=None):
        if self.finished:
            return
        self.finished = True
        if nonstream:
            try:
                self.observe(json.loads(nonstream), streamed=False)
            except (ValueError, TypeError):
                error = error or 'response was not completion JSON'
        elapsed = time.monotonic() - self.row['t_send_monotonic']
        ni, no, source = counts(self.usage, self.timings)
        stream = bool(self.row['request'].get('stream'))
        ok = status == 200 and not error and (not stream or self.done or self.finish_reason is not None)
        self.row.update(http_status=status, ok=ok, error=error, elapsed_s=elapsed,
                        t_done_unix=time.time(), ttft_s=self.first, last_event_s=self.last,
                        input_tokens=ni, output_tokens=no, token_count_source=source,
                        usage=self.usage, timings=self.timings, finish_reason=self.finish_reason,
                        text=''.join(self.text), reasoning=''.join(self.reasoning),
                        stream_completed=self.done if stream else None,
                        **rates(no, elapsed, self.first, self.last))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock, self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(self.row, ensure_ascii=False) + '\n')


def summary(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()] if Path(path).exists() else []
    valid = [r for r in rows if r['ok'] and r['output_tokens'] is not None]
    elapsed = max((r['t_send_monotonic'] + r['elapsed_s'] for r in rows), default=0) - min(
        (r['t_send_monotonic'] for r in rows), default=0)
    complete_counts = len(valid) == len(rows) and bool(rows)
    return {'requests': len(rows), 'failed': sum(not r['ok'] for r in rows),
            'missing_token_counts': sum(r['output_tokens'] is None for r in rows),
            'finish_length': sum(r['finish_reason'] == 'length' for r in rows),
            'output_tokens': sum(r['output_tokens'] for r in valid),
            'window_s': elapsed,
            'service_output_tok_s': sum(r['output_tokens'] for r in valid) / elapsed if complete_counts and elapsed > 0 else None,
            'service_definition': 'all observed successful output tokens / first send to last completion, including client gaps; not saturation capacity',
            'request_metrics': 'requests.jsonl; E2E includes prefill/wait; client decode is event-boundary estimate'}


def analyze_run(folder):
    """Recompute per-tool truncation and rate summaries offline from original requests."""
    root = Path(folder)
    report = json.loads((root / 'report.json').read_text())
    rows = [json.loads(line) for line in (root / 'requests.jsonl').read_text(encoding='utf-8').splitlines()]
    groups = {}
    for row in rows:
        name = 'probe_or_profile'
        for bench in report['benchmarks']:
            if bench.get('t_start', float('inf')) <= row['t_send_unix'] <= bench.get('t_end', 0):
                name = bench['benchmark']
                break
        if name == 'probe_or_profile' and row['request'].get('logprobs') is not None:
            name = 'token_probs'
        groups.setdefault(name, []).append(row)
    result = {}
    for name, records in groups.items():
        def mean(key):
            values = [r[key] for r in records if r.get(key) is not None and r['ok']]
            return sum(values) / len(values) if values else None
        result[name] = {'requests': len(records), 'failed': sum(not r['ok'] for r in records),
                        'missing_counts': sum(r['output_tokens'] is None for r in records),
                        'finish_length': sum(r['finish_reason'] == 'length' for r in records),
                        'mean_request_e2e_output_tok_s': mean('e2e_output_tok_s'),
                        'mean_client_decode_estimate_tok_s': mean('decode_tok_s_client_estimate'),
                        'note': 'request mean, not aggregate service capacity; fixed-length performance/probability runs may intentionally end at length',
                        'request_ids': [r['request_id'] for r in records]}
    samples = root / 'samples.jsonl'
    if samples.exists():
        raw = [json.loads(line) for line in samples.read_text().splitlines()]
        result['worker_memory'] = {'peak_tree_pss_gib': max((s.get('tree_pss_gib', 0) for s in raw), default=None),
                                   'max_processes_observed': max((len(s.get('process_tree', [])) for s in raw), default=0),
                                   'note': 'sampled process PSS, not added to CUDA buffers; short-lived workers may escape sampling'}
    (root / 'request-analysis.json').write_text(json.dumps(result, indent=2))
    return result
