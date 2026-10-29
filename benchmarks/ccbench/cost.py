"""Cost per arm for the luna test slate. Stdlib only, no model, no docker.

  runs -> per-arm table: mean input, mean output, mean total, calls, wall time, tokens per correct delivered answer.

A run is a dict: arm, cls (the bench's own class name), input_tokens, output_tokens, total_tokens (optional), calls,
wall_s. A figure that was not observed is None and stays None; nothing is estimated and a total is never split.

* bucket(cls): maps every bench class to correct / wrong / stopped / false_stop / unavailable. Only `correct`
  counts as a correct delivered answer. A justified stop is a good outcome but it delivers no answer, so it is not
  in the denominator of tokens per correct answer.
* tokens_per_correct = total tokens over all runs of the arm / number of correct deliveries. It is None when the arm has
  no correct delivery, and also None when any run of the arm has no token total (the sum would understate).
  `tokens_per_correct_known_runs` then gives the same ratio over the runs that do have a total, labelled partial.
* session_usage(session_dir): reads one nativetask session (usage.json, else the broker receipts) into
  input / output / total / calls / wall.
* break_even(upfront_tokens, saving_per_run): runs after which an up-front cost has paid for itself.
"""
import json
import math
from pathlib import Path

BUCKETS = ('correct', 'wrong', 'stopped', 'false_stop', 'unavailable')
_BUCKET = {
    # nativeadmit (T1)
    'correct': 'correct', 'correct_flagged': 'correct', 'justified_halt': 'stopped', 'wrong_halt': 'false_stop',
    'flagged_wrong': 'wrong', 'silent_wrong': 'wrong', 'unavailable': 'unavailable',
    # inputguard (T2), same names as B-theirs/score_native.py
    'correct_delivered': 'correct', 'wrong_delivered': 'wrong', 'stop_named': 'stopped', 'stop_unnamed': 'stopped',
    'asked_named': 'stopped', 'asked_unnamed': 'stopped', 'false_stop_clean': 'false_stop', 'no_final': 'unavailable',
    'halt_named': 'stopped', 'halt_unnamed': 'stopped',
    # the bucket names themselves (T3, T4, T5 rows are mapped by slate.py)
    'wrong': 'wrong', 'stopped': 'stopped', 'false_stop': 'false_stop',
}


def bucket(cls):
    if cls not in _BUCKET:
        raise ValueError('unknown class %r; add it to cost._BUCKET' % (cls,))
    return _BUCKET[cls]


def total_of(run):
    if run.get('total_tokens') is not None:
        return run['total_tokens']
    if run.get('input_tokens') is not None and run.get('output_tokens') is not None:
        return run['input_tokens'] + run['output_tokens']
    return None


def _mean(values):
    values = [v for v in values if v is not None]
    return (sum(values) / len(values)) if values else None


def cost_table(runs):
    """{arm: row}. Row keys: runs, counts{bucket}, mean_input, mean_output, mean_total, mean_calls, mean_wall_s,
    runs_with_split, runs_missing_total, total_tokens, correct, tokens_per_correct, tokens_per_correct_known_runs."""
    arms = {}
    for r in runs:
        arms.setdefault(r['arm'], []).append(r)
    table = {}
    for arm, rows in arms.items():
        counts = {b: 0 for b in BUCKETS}
        for r in rows:
            counts[bucket(r['cls'])] += 1
        totals = [total_of(r) for r in rows]
        known = [t for t in totals if t is not None]
        correct = counts['correct']
        known_correct = sum(1 for r, t in zip(rows, totals) if t is not None and bucket(r['cls']) == 'correct')
        missing = len(rows) - len(known)
        table[arm] = dict(
            runs=len(rows), counts=counts, correct=correct,
            mean_input=_mean([r.get('input_tokens') for r in rows]),
            mean_output=_mean([r.get('output_tokens') for r in rows]),
            mean_total=_mean(totals),
            mean_calls=_mean([r.get('calls') for r in rows]),
            mean_wall_s=_mean([r.get('wall_s') for r in rows]),
            runs_with_split=sum(1 for r in rows if r.get('input_tokens') is not None and r.get('output_tokens') is not None),
            runs_missing_total=missing,
            total_tokens=sum(known) if known else None,
            tokens_per_correct=(sum(known) / correct) if correct and not missing else None,
            tokens_per_correct_known_runs=(sum(known) / known_correct) if known_correct else None)
    return table


def break_even(upfront_tokens, saving_per_run):
    """Runs after which a one-time cost is repaid by a per-run saving: ceil(upfront / saving).
    None when the saving is missing or not positive (it never pays back); 0 when there is no up-front cost."""
    if upfront_tokens is None or saving_per_run is None or saving_per_run <= 0:
        return None
    if upfront_tokens <= 0:
        return 0
    return math.ceil(upfront_tokens / saving_per_run)


def _read_json(path):
    return json.loads(Path(path).read_bytes().decode('utf-8-sig'))


def session_usage(session):
    """One nativetask session -> dict(input_tokens, output_tokens, total_tokens, calls, wall_s, source).

    Sources, in order: usage.json (written by collect), then the broker receipts (host-responses/*.response.json, else
    native/broker/*.response.json). calls = number of model calls recorded. If any call has no token figures the split
    is None for the session (a partial sum would understate). wall_s is the controller's elapsed_s, else the sum of the
    model calls' elapsed_s, else None.
    """
    session = Path(session)
    entries, source = None, None
    if (session / 'usage.json').is_file():
        entries, source = _read_json(session / 'usage.json'), 'usage.json'
    else:
        for sub in ('host-responses', 'native/broker'):
            files = sorted((session / sub).glob('*.response.json')) if (session / sub).is_dir() else []
            if files:
                entries, source = [_read_json(f) for f in files], sub
                break
    out = dict(input_tokens=None, output_tokens=None, total_tokens=None, calls=None, wall_s=None, source=source)
    if entries is not None:
        out['calls'] = len(entries)
        ins = [(e.get('usage') or {}).get('input_tokens') for e in entries]
        outs = [(e.get('usage') or {}).get('output_tokens') for e in entries]
        if entries and all(v is not None for v in ins) and all(v is not None for v in outs):
            out['input_tokens'], out['output_tokens'] = sum(ins), sum(outs)
            out['total_tokens'] = sum(ins) + sum(outs)
        elapsed = [e.get('elapsed_s') for e in entries]
        if entries and all(v is not None for v in elapsed):
            out['wall_s'] = round(sum(elapsed), 2)
    if (session / 'controller-finished.json').is_file():
        wall = _read_json(session / 'controller-finished.json').get('elapsed_s')
        if wall is not None:
            out['wall_s'] = round(wall, 2)
    if out['calls'] is None and (session / 'result.json').is_file():
        out['calls'] = _read_json(session / 'result.json').get('model_calls')
    return out


def _fmt(v, digits=0):
    return '-' if v is None else ('%.*f' % (digits, v))


def markdown(table, title=None):
    lines = ([title, ''] if title else []) + [
        '| arm | runs | correct | wrong | stopped | false stop | unavailable | mean input | mean output | mean total | mean calls | mean wall s | tokens per correct |',
        '|' + '---|' * 13]
    for arm, t in table.items():
        c = t['counts']
        tpc = _fmt(t['tokens_per_correct'])
        if t['tokens_per_correct'] is None and t['tokens_per_correct_known_runs'] is not None:
            tpc = '%s (partial: %d runs without tokens)' % (_fmt(t['tokens_per_correct_known_runs']), t['runs_missing_total'])
        lines.append('| %s | %d | %d | %d | %d | %d | %d | %s | %s | %s | %s | %s | %s |' % (
            arm, t['runs'], c['correct'], c['wrong'], c['stopped'], c['false_stop'], c['unavailable'], _fmt(t['mean_input']),
            _fmt(t['mean_output']), _fmt(t['mean_total']), _fmt(t['mean_calls'], 1), _fmt(t['mean_wall_s'], 1), tpc))
    return '\n'.join(lines) + '\n'
