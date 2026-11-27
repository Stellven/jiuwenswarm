"""Separate, unscored warm-up requests on the target lab's resident Muse server."""

import hashlib
import json
import math

from jiuwenswarm.factory.lab_lifecycle import atomic_json
from jiuwenswarm.factory.muse_r9_measure import first_cached_tasks, quiet_request, read_log
from scripts.factory import lab_v4_fast as lab
from scripts.factory.r8_derive_p_ttft import derive
from scripts.factory.warmup_w1 import document_shell, fit_notebook

WARMUP_FILE = 'warmup.json'
FORMAT = 'muse-target-warmup/1'
LIMIT = 6
DECODE_TOLERANCE = 0.10
PREDICT = 32
NOTEBOOKS = (
    'telescope eyepiece lens star comet observatory finder prism mirror orbit shadow aperture mount sky',
    'archive atlas register ledger memorandum folio stamp correspondence catalogue spine shelf index ink map',
    'truss pulley bearing bolt wire brace rail crank shaft bushing hinge lever screw clamp pylon joist',
    'loom heddle shuttle warp weft skein cotton tapestry frame spool hemp thread wool silk needle bobbin',
    'tram depot platform ferry tunnel siding track timetable route terminal station siding bridge conductor',
    'microscope slide coverslip pipette reagent flask vial plate filter buffer tissue dropper solution beaker',
)


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _ids_sha(tokens):
    return _sha(json.dumps(tokens, separators=(',', ':')))


def _tokenize(server, text):
    response = server.post(dict(content=text, add_special=True, parse_special=True),
                           path='/tokenize', timeout=60)
    tokens = response.get('tokens')
    if not isinstance(tokens, list) or not tokens or any(type(token) is not int for token in tokens):
        raise ValueError('Target tokenizer did not return valid token IDs')
    return tuple(tokens)


def _positive(value):
    return type(value) in (float, int) and math.isfinite(value) and value > 0


def _stable(previous, latest):
    return max(previous, latest) <= min(previous, latest) * (1 + DECODE_TOLERANCE)


def _summary(rows, reason):
    latest = rows[-1]['decode_tokens_per_second']
    count = len(rows)
    if reason == 'stable':
        return f'warm-up: {count} requests, stable at {latest:.2f} tok/s'
    return f'warm-up: {count} requests, stability not reached (last {latest:.2f} tok/s)'


def _logged_request(tasks, count):
    if (len(tasks) != 1 or tasks[0].get('slot_id') != 0 or type(tasks[0].get('cached_tokens')) is not int
            or tasks[0]['cached_tokens'] != 0 or tasks[0].get('prompt_tokens') != count or not tasks[0].get('end')):
        raise ValueError('Warm-up requires one completed request with zero initial cached tokens')
    return tasks[0]


def _clocks(row):
    inputs = dict(row, arm='target', request=f'warmup-{row["index"]}', state='warmup', repeat=0)
    return derive(inputs)


def run(server, monitor, output, *, template, measured_prompts):
    """Warm the open server once. The caller measures only after this phase returns."""
    path = output / WARMUP_FILE
    if path.exists():
        raise ValueError('Warm-up evidence already exists for this server load')
    measured = sorted(set(measured_prompts))
    report = dict(format=FORMAT, status='preparing', requests=[], stop_reason=None,
                  request_cap=LIMIT, decode_relative_tolerance=DECODE_TOLERANCE,
                  tolerance_denominator='slower adjacent decode rate',
                  measured_prompt_sha256=sorted(_sha(text) for text in measured))
    atomic_json(path, report)
    try:
        head, tail = document_shell(template)
        target = len(_tokenize(server, template))
        tokenize = lambda text: _tokenize(server, text)
        seen_text = set(measured)
        seen_ids = {tokenize(text) for text in measured}
        report['measured_token_ids_sha256'] = sorted(_ids_sha(ids) for ids in seen_ids)
        report['target_tokens'] = target
        report['status'] = 'running'
        for index, words in enumerate(NOTEBOOKS, 1):
            prompt, tokens = fit_notebook(head, tail, words, tokenize, target)
            if prompt in seen_text or tokens in seen_ids:
                raise ValueError('A warm-up document overlaps a measured or previous warm-up prompt')
            seen_text.add(prompt)
            seen_ids.add(tokens)
            row = dict(index=index, prompt=prompt, prompt_sha256=_sha(prompt), token_ids_sha256=_ids_sha(tokens),
                       rendered_prompt_tokens=len(tokens), cache_prompt=False, measured_cell=False,
                       n_predict=PREDICT, temperature=0, seed=1, ignore_eos=True, status='pending')
            report['requests'].append(row)
            atomic_json(path, report)
            offset = server.log.stat().st_size
            metrics, evidence, error = quiet_request(monitor, lambda: lab.request(
                server, prompt, PREDICT, benchmark=True, cache_prompt=False))
            row['quiet'] = evidence
            row['server_log_start'] = offset
            raw = read_log(server, offset)
            row['server_log_end'] = offset + len(raw)
            if metrics:
                row.update(metrics)
            if error:
                raise error
            task = _logged_request(first_cached_tasks(raw), len(tokens))
            row['server_request'] = task
            if (row['prompt_tokens'] != target or row['generated_tokens'] != PREDICT
                    or not all(_positive(row.get(key)) for key in (
                        'client_ttft_ms', 'decode_tokens_per_second', 'request_total_ms'))):
                raise ValueError('Warm-up response has invalid token counts or timing')
            clocks = _clocks(row)
            row.update(derived_ttft_ms=clocks['derived_ttft_ms'],
                       direct_client_ttft_ms=clocks['direct_client_ttft_ms'], status='complete')
            if index > 1 and _stable(report['requests'][-2]['decode_tokens_per_second'],
                                     row['decode_tokens_per_second']):
                report['stop_reason'] = 'stable'
                break
            atomic_json(path, report)
        report['stop_reason'] = report['stop_reason'] or 'cap_reached'
        report['status'] = 'complete'
        report['summary'] = _summary(report['requests'], report['stop_reason'])
        server.run.log(report['summary'])
    except BaseException as error:
        report.update(status='stopped', stop_reason='request_or_evidence_error',
                      error=dict(code=getattr(error, 'code', type(error).__name__), message=str(error)))
        if report['requests'] and report['requests'][-1]['status'] == 'pending':
            report['requests'][-1]['status'] = 'stopped'
        raise
    finally:
        atomic_json(path, report)
    return report


def validate(report, raw_log, first_measured_offset, measured_prompts):
    """Recheck completion, disjointness and the stopping rule from sealed evidence."""
    rows = report['requests']
    measured = {_sha(text) for text in measured_prompts}
    if (report['format'] != FORMAT or report['status'] != 'complete' or not 2 <= len(rows) <= LIMIT
            or report['request_cap'] != LIMIT or report['decode_relative_tolerance'] != DECODE_TOLERANCE
            or report['measured_prompt_sha256'] != sorted(measured)):
        raise ValueError('Warm-up protocol or measured prompt identity differs')
    seen_text = set(measured)
    seen_ids = set(report['measured_token_ids_sha256'])
    target = report['target_tokens']
    previous_end = 0
    logged = []
    for index, row in enumerate(rows, 1):
        sha = row['prompt_sha256']
        ids = row['token_ids_sha256']
        start, end = row['server_log_start'], row['server_log_end']
        if (row['index'] != index or row['status'] != 'complete' or row['cache_prompt'] is not False
                or row['measured_cell'] is not False or row['n_predict'] != PREDICT
                or sha != _sha(row['prompt']) or sha in seen_text or ids in seen_ids
                or not 0 <= previous_end <= start < end <= first_measured_offset <= len(raw_log)
                or row['prompt_tokens'] != target or row['rendered_prompt_tokens'] != target
                or row['generated_tokens'] != PREDICT
                or not all(_positive(row.get(key)) for key in (
                    'client_ttft_ms', 'decode_tokens_per_second', 'request_total_ms'))):
            raise ValueError('Warm-up row overlaps a measured prompt or has invalid timing or identity')
        seen_text.add(sha)
        seen_ids.add(ids)
        task = _logged_request(first_cached_tasks(raw_log[start:end]), row['rendered_prompt_tokens'])
        if task != row['server_request']:
            raise ValueError('Warm-up server log differs from its recorded request')
        clocks = _clocks(row)
        if any(row[key] != clocks[key] for key in ('derived_ttft_ms', 'direct_client_ttft_ms')):
            raise ValueError('Warm-up timing differs from its recorded stream')
        logged.append(task)
        previous_end = end
    if first_cached_tasks(raw_log[:first_measured_offset]) != logged:
        raise ValueError('Unexpected requests before the measured campaign')
    adjacent = [idx for idx, (before, after) in enumerate(zip(rows, rows[1:]), 2)
                if _stable(before['decode_tokens_per_second'], after['decode_tokens_per_second'])]
    reason = report['stop_reason']
    if ((reason == 'stable' and adjacent == [len(rows)])
            or (reason == 'cap_reached' and len(rows) == LIMIT and not adjacent)):
        if report['summary'] == _summary(rows, reason):
            return report['summary']
    raise ValueError('Warm-up report does not match the first stable pair or the request cap')
