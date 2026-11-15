"""Read-only, descriptive CC job accounting over retained telemetry/snapshots.

No inferred alias ownership, retry detection from repeated calls, or causal scores.
The command reads exported JSONL, never opens or reconciles a live factory Store.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SCHEMA = 'factory.cc-job-metrics/1'


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _timing(values):
    measured = sorted(v for v in values if _number(v))
    return dict(measured=len(measured), unknown=len(values) - len(measured),
                total=sum(measured) if measured else None,
                p50=measured[math.ceil(len(measured) * .5) - 1] if measured else None,
                p95=measured[math.ceil(len(measured) * .95) - 1] if measured else None,
                maximum=max(measured) if measured else None)


def _calls(rows):
    outcomes = [row.get('outcome') for row in rows]
    return dict(calls=len(rows), succeeded=outcomes.count('ok'), failed=outcomes.count('error'),
                unknown_outcome=sum(v not in {'ok', 'error'} for v in outcomes),
                duration_ms=_timing([r.get('duration_ms') for r in rows]),
                error_codes={code: sum(r.get('error_code') == code for r in rows)
                             for code in sorted({r.get('error_code') for r in rows
                                                 if isinstance(r.get('error_code'), str)})})


def analyze(events, attempts=(), *, include_replay=False):
    """Keep package spans and backend spans separate; join jobs by explicit ID.

    Optional attempts are exported durable attempt objects. Their history is the
    only retry source. Submission ownership requires a successful submit receipt;
    status/result polling never assigns ownership. Conflicting owners are unknown.
    """
    source = list(events)
    events = [e for e in source if isinstance(e, dict) and (include_replay or not e.get('replay'))]
    groups, backend, owners, ownership_methods = {}, {}, {}, {}
    for row in events:
        event = row.get('event')
        if event == 'cc.call':
            key = (row.get('capsule'), row.get('capability'), row.get('capsule_version'), row.get('release_sha256'))
            backend.setdefault(key, []).append(row)
        if event == 'cc.job_call':
            key = (row.get('invoked_capsule'), row.get('invoked_capsule_version'),
                   row.get('invoked_release_sha256'))
            groups.setdefault(key, []).append(row)
            route = row.get('backend_capability')
            attempt_id = row.get('attempt_id')
            child_receipt = (route == 'factory_loop.execute'
                and row.get('attempt_attribution') == 'loop_child_receipt'
                and isinstance(row.get('attempt_task_id'), str) and bool(row['attempt_task_id']))
            if (row.get('outcome') == 'ok' and isinstance(route, str)
                    and (route.endswith(('.submit', '.ab_submit')) or child_receipt)
                    and isinstance(attempt_id, str) and attempt_id):
                identity = (row['attempt_task_id'] if child_receipt else row.get('task_id'), attempt_id)
                owners.setdefault(identity, set()).add(key)
                ownership_methods.setdefault(identity, set()).add('loop_child_receipt' if child_receipt else 'submit_receipt')
    # Deduplicate transitions by durable task/attempt identity, not capability call.
    jobs = {}
    for row in events:
        if row.get('event') == 'job.transition' and row.get('attempt_id'):
            key = (row.get('task_id'), row['attempt_id'])
            job = jobs.setdefault(key, dict(task_id=key[0], attempt_id=key[1], kind=row.get('kind'),
                                           state=None, queue_wait_s=None, run_s=None, retry_of=None,
                                           retry_known=False, build_results=[]))
            job['state'] = row.get('to')
            for field in ('queue_wait_s', 'run_s'):
                if _number(row.get(field)):
                    job[field] = row[field]
    for row in attempts:
        key = (row.get('task_id'), row.get('attempt_id'))
        if not key[1]:
            continue
        job = jobs.setdefault(key, dict(task_id=key[0], attempt_id=key[1], queue_wait_s=None,
                                       run_s=None, build_results=[]))
        job.update(kind=row.get('kind'), state=row.get('state'))
        history = row.get('history')
        job['retry_known'] = isinstance(history, list)
        job['retry_of'] = next((h['retry_of'] for h in reversed(history or [])
                                if isinstance(h, dict) and h.get('retry_of')), None)
        started, ended = row.get('started'), row.get('ended')
        queued = history[0].get('created') if history and isinstance(history[0], dict) else None
        for field, start, end in (('queue_wait_s', queued, started), ('run_s', started, ended)):
            if not _number(job.get(field)) and _number(start) and _number(end) and end >= start:
                job[field] = end - start
    unlinked_results = []
    for row in events:
        if row.get('event') != 'build.result':
            continue
        key = (row.get('task_id'), row.get('attempt_id'))
        if key in jobs:
            # A result's record ID is stable across repeated exports.
            if not any(r.get('record_id') == row.get('record_id') and row.get('record_id')
                       for r in jobs[key]['build_results']):
                jobs[key]['build_results'].append(row)
        else:
            unlinked_results.append(row)
    for key, job in jobs.items():
        ownership = owners.get(key, set())
        job['owner'] = next(iter(ownership)) if len(ownership) == 1 else None
        methods = ownership_methods.get(key, set())
        job['ownership'] = ((next(iter(methods)) if len(methods) == 1 else 'multiple_explicit_receipts')
                            if len(ownership) == 1 else 'conflicting' if ownership else 'unknown')

    def job_metrics(rows):
        results = [r for job in rows for r in job['build_results']]
        cache = [r.get('cache_hit') for r in results]
        return dict(attempts=len(rows), succeeded=sum(j['state'] == 'succeeded' for j in rows),
                    failed=sum(j['state'] == 'failed' for j in rows),
                    cancelled=sum(j['state'] == 'cancelled' for j in rows),
                    nonterminal_or_unknown=sum(j['state'] not in {'succeeded', 'failed', 'cancelled'} for j in rows),
                    queue_wait_s=_timing([j.get('queue_wait_s') for j in rows]),
                    run_s=_timing([j.get('run_s') for j in rows]),
                    retries=dict(observed=sum(bool(j.get('retry_of')) for j in rows),
                                 unknown=sum(not j.get('retry_known') for j in rows)),
                    build_wall_s=_timing([r.get('wall_s') for r in results]),
                    build_results=len(results),
                    base_image_cache=dict(hit=sum(v is True for v in cache), miss=sum(v is False for v in cache),
                                          unknown=sum(type(v) is not bool for v in cache)))

    packages = []
    for key, rows in sorted(groups.items(), key=lambda item: tuple(str(v) for v in item[0])):
        packages.append(dict(capsule=key[0], capsule_version=key[1], release_sha256=key[2],
            **_calls(rows), jobs=job_metrics([j for j in jobs.values() if j['owner'] == key]),
            capabilities=[dict(capability=cap, **_calls([r for r in rows if r.get('invoked_capability') == cap]))
                          for cap in sorted({r.get('invoked_capability') for r in rows}, key=str)]))
    return dict(schema=SCHEMA, descriptive_only=True, packages=packages,
        backends=[dict(capsule=key[0], capability=key[1], capsule_version=key[2], release_sha256=key[3], **_calls(rows))
                  for key, rows in sorted(backend.items(), key=lambda item: str(item[0]))],
        jobs=job_metrics(list(jobs.values())),
        unattributed_jobs=job_metrics([j for j in jobs.values() if j['owner'] is None]),
        job_attribution=[dict(task_id=j['task_id'], attempt_id=j['attempt_id'], kind=j.get('kind'),
            state=j.get('state'), ownership=j['ownership'],
            owner=dict(capsule=j['owner'][0], capsule_version=j['owner'][1], release_sha256=j['owner'][2])
                  if j['owner'] else None)
            for _, j in sorted(jobs.items(), key=lambda item: str(item[0]))],
        unlinked_build_results=len(unlinked_results),
        excluded_replay_events=sum(bool(e.get('replay')) for e in source if isinstance(e, dict)) if not include_replay else 0,
        limitations=['Call, backend, queue, run and build spans can overlap; do not add them.',
            'Missing completion events and telemetry write failures are not recoverable from this stream.',
            'Legacy backend calls do not establish invoked package identity.',
            'Repeated calls, polls and idempotent submits are not evidence of retries.',
            'Cache hit means recorded base-image preparation availability, not compiler cache effectiveness.',
            'Durations and failures describe retained work, not correctness, usefulness or causal improvement.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', required=True, type=Path, help='Exported telemetry JSONL')
    parser.add_argument('--attempts', type=Path, help='Optional JSON array of durable attempt snapshots')
    parser.add_argument('--include-replay', action='store_true')
    args = parser.parse_args()
    events = [json.loads(line) for line in args.events.read_text().splitlines() if line.strip()]
    attempts = json.loads(args.attempts.read_text()) if args.attempts else []
    print(json.dumps(analyze(events, attempts, include_replay=args.include_replay), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
