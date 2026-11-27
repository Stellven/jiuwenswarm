"""Recover the first sampled token's approximate client arrival from P's two clocks."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def derive(row):
    progress = row['prompt_progress']
    initially_cached = progress[0].get('cache', 0) if progress else 0
    if (not progress or progress[0]['processed'] != initially_cached
            or progress[-1]['processed'] != row['prompt_tokens'] + initially_cached):
        raise ValueError('Missing start or completion of the recorded prefill')
    if 'stream_arrivals' in row:
        anchor = next(e['elapsed_ms'] for e in row['stream_arrivals'] if e['progress'])
    else:
        anchor = row['client_ttft_ms']
    first_progress = progress[0]['time_ms']
    prompt = row['prompt_ms']
    estimate = anchor + prompt - first_progress
    if not all(math.isfinite(v) for v in (anchor, first_progress, prompt, estimate)) or not 0 < estimate < row['request_total_ms']:
        raise ValueError('Invalid TTFT clock anchors')
    return dict(arm=row['arm'], request=row['request'], state=row['state'], repeat=row['repeat'],
                quiet_status=row['quiet']['status'], recorded_first_progress_arrival_ms=anchor,
                server_elapsed_at_first_progress_ms=first_progress, server_elapsed_at_first_sampled_token_ms=prompt,
                derived_ttft_ms=round(estimate, 1),
                **(dict(direct_client_ttft_ms=row['client_ttft_ms'],
                        derived_minus_direct_ms=round(estimate-row['client_ttft_ms'], 1))
                   if 'stream_arrivals' in row and row['client_ttft_ms'] is not None else {}))


def main(source, dest, retained_baseline=False):
    raw = source.read_bytes()
    d = json.loads(raw)
    if source.resolve() == dest.resolve():
        raise ValueError('A separate output is required')
    if retained_baseline:
        if d['leg']['id'] != '5' or d['leg']['role'] != 'A+P':
            raise ValueError('Expected baseline load 5')
        selected = [(i,row) for i,row in enumerate(d['rows']) if row['request'] in ('p512','p2048')]
        keys = {(r['request'], r['state'], r['repeat']) for _,r in selected}
        expected = {(p,state,rep) for p in ('p512','p2048') for state,rep in (('cold',0),('warm',1),('warm',2))}
        if keys != expected or len(selected) != 6 or any('stream_arrivals' not in r for _,r in selected):
            raise ValueError('Missing baseline rows or direct client clock evidence')
    else:
        if d['status'] != 'completed' or d['leg']['role'] != 'P':
            raise ValueError('Expected completed P speed report')
        selected = list(enumerate(d['rows']))
    rows = [dict(source_pointer=f'/rows/{i}', **derive(row)) for i,row in selected]
    report = dict(schema='r8-derived-ttft/1', source=source.name, source_sha256=hashlib.sha256(raw).hexdigest(),
                  method='Derived first-token time. Anchor the server clock to the client arrival of the first prompt-progress event. Add the elapsed server interval from that event to first token sampling. The delivered server includes sampling the first token in prompt_ms.',
                  formula='recorded_first_progress_arrival_ms + prompt_ms - first_prompt_progress.time_ms',
                  limitation='P did not retain individual generated-content client arrival times. Network delivery and any gap before the first nonempty token cannot be recovered exactly.',
                  engine_source_commit='17e4594f0bfb7eacd3ce5d2d0dd16fb61ba9f817',
                  engine_evidence=['tools/server/server-context.cpp:2289', 'tools/server/server-context.cpp:4807',
                                   'tools/server/server-common.h:475'], rows=rows)
    with dest.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('dest', type=Path)
    parser.add_argument('--retained-baseline', action='store_true')
    args = parser.parse_args()
    main(args.source, args.dest, args.retained_baseline)
