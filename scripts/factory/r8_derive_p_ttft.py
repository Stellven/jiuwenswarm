"""Recover the first sampled token's approximate client arrival from P's two clocks."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def derive(row):
    progress = row['prompt_progress']
    if not progress or progress[0]['processed'] != 0 or progress[-1]['processed'] != row['prompt_tokens']:
        raise ValueError('Missing start or completion of the recorded prefill')
    anchor = row['client_ttft_ms']
    first_progress = progress[0]['time_ms']
    prompt = row['prompt_ms']
    estimate = anchor + prompt - first_progress
    if not all(math.isfinite(v) for v in (anchor, first_progress, prompt, estimate)) or not 0 < estimate < row['request_total_ms']:
        raise ValueError('Invalid TTFT clock anchors')
    return dict(arm=row['arm'], request=row['request'], state=row['state'], repeat=row['repeat'],
                quiet_status=row['quiet']['status'], recorded_first_progress_arrival_ms=anchor,
                server_elapsed_at_first_progress_ms=first_progress, server_elapsed_at_first_sampled_token_ms=prompt,
                derived_ttft_ms=round(estimate, 1))


def main(source, dest):
    raw = source.read_bytes()
    d = json.loads(raw)
    if source.resolve() == dest.resolve() or d['status'] != 'completed' or d['leg']['role'] != 'P':
        raise ValueError('A separate destination and completed P speed report are required')
    rows = [dict(source_pointer=f'/rows/{i}', **derive(row)) for i, row in enumerate(d['rows'])]
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
    args = parser.parse_args()
    main(args.source, args.dest)
