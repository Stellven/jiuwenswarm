"""Run the operator-paced, CPU-only recorder evidence verification."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import time

from jiuwenswarm.factory.controller import Controller
from jiuwenswarm.factory.store import Store


TEMPLATE = 'recorder-evidence-walkthrough'
SOURCE_TASK = 'spark-star-observability-event-recorder'
PREFIX = 'spark-c1-functional/'
STEP_SECONDS = 45
PINS = {
    'report-v3.md': '6e377d2669325498bd1986310ed7eb25158e04560d8a26e3c9fd77cc3b0cef7e',
    'c1-recorder-off-01/result.json': 'c7f67708cba63aafcf5102633bb14ae0fadb0953db8a0830513e11e847d562ee',
    'c1-recorder-on-01/result.json': '8b76db6310ba9e42f60f35b82f6677080233e5271b923aea3468719adb3d417c',
    'c1-recorder-off-01/parity-512-result.json': 'e19f4fd735eae00678c405268872473f5b5e2a2137b019648a4ea1862249f738',
    'c1-recorder-on-01/parity-512-result.json': 'd1be0a337821a1f6e7c8f6964f7588dd512315f3cdfc163589e19b12e992fefa',
    'events.jsonl': 'd1f0f799ff4c543b70bfafe122845c70b8b6c09ec3b24c5935835fdf8bf73abb',
    'granite-score-02/fixture-evidence.json': '9cd94befa5ff78e3cf6fb7d644d3941dba9bba6731e6e294e5a60e64f9629d4c',
    'granite-score-02/S6/C1/events.jsonl': 'b6cb2de8025ac011e12d727a3b6c4ffcb9292c7fe126cb76ecd90133512275e5',
    'granite-score-02/S6/C2/events.jsonl': '8cdc3db6ffd9b6369985f634f5f7aa878739f4569604ef73e93ccd0808471b28',
}


def require(condition, error):
    if not condition:
        raise ValueError(error)


def valid_template(task):
    return task['operator_labels'].get('native_demo') == TEMPLATE and not task['allowed_effects'] and task['budget'] == {
        'max_turns': 1, 'wall_clock_s': 270}


def trace(raw, layer_count):
    rows = [json.loads(line) for line in raw.splitlines()]
    *events, terminal = rows
    require(terminal['type'] == 'summary' and all(row['type'] == 'event' for row in events), 'Trace terminal summary is missing')
    keys = {(row['microbatch'], row['layer']) for row in events}
    by_phase = Counter(row['phase'] for row in events)
    require(len(keys) == len(events) == terminal['written'] and terminal['expected'] == len(events) + terminal['lost'],
            'Route rows do not reconcile with the terminal summary')
    batch_layers = defaultdict(set)
    for batch, layer in keys:
        batch_layers[batch].add(layer)
    layers = set(range(layer_count))
    require(all(seen <= layers for seen in batch_layers.values()), 'Unexpected route layer')
    missing = {batch: sorted(layers - seen) for batch, seen in sorted(batch_layers.items()) if seen != layers}
    return dict(written=len(events), expected=terminal['expected'], lost=terminal['lost'], route_lost=terminal['route_lost'],
                event_rows_by_phase=dict(by_phase), missing_layers=missing)


class RecorderVerification:
    def __init__(self, source, destination, task_id, transcript):
        self.source, self.destination, self.task_id, self.transcript = source, destination, task_id, transcript
        self.result = {}

    def read(self, name):
        raw = self.source.artifact_bytes(SOURCE_TASK, PREFIX + name)
        require(hashlib.sha256(raw).hexdigest() == PINS[name], f'Pinned artifact changed: {name}')
        media = {'.md': 'text/markdown', '.jsonl': 'application/x-ndjson', '.json': 'application/json'}
        self.destination.put_artifact(self.task_id, name, raw, media[Path(name).suffix], None)
        return raw

    def progress(self, key, message, sources=()):
        with self.transcript.open('a', encoding='utf-8') as log:
            log.write(json.dumps(dict(event='native.progress', t=time.time(), content=message)) + '\n')
        self.destination.append_observation(self.task_id, dict(obs_id=key, kind='recorder_evidence_check',
            values=dict(message=message), source_artifacts=list(sources)))

    def report_pin(self):
        name = 'report-v3.md'
        self.read(name)
        self.progress('report-pinned', 'Verified the stored recorder report digest against its published pin.', [name])

    def parity(self):
        names = [f'c1-recorder-{arm}-01/{name}.json' for arm in ('off', 'on') for name in ('result', 'parity-512-result')]
        off, off_text, on, on_text = (json.loads(self.read(name)) for name in names)
        require(all(r['scope_verified'] and r['returncode'] == 0 and r['reason'] is None and
                    not any(int(r['memory_events'].get(k, 0)) for k in ('oom', 'oom_kill', 'oom_group_kill')) for r in (off, on)),
                'The recorder parity caps are not clean')
        require(all(r['ok'] and r['usage']['prompt_tokens'] == 512 and r['usage']['completion_tokens'] == 32 for r in (off_text, on_text)) and
                all(off_text[k] == on_text[k] for k in ('output_sha256', 'reasoning_sha256')), 'The archived output digests differ')
        self.result['deepseek_greedy_parity'] = True
        self.progress('parity-checked', 'Verified matching 512-token DeepSeek output and reasoning hashes with the recorder on and off.', names)

    def deepseek(self):
        name = 'events.jsonl'
        result = trace(self.read(name), 40)
        require(result['written'] == result['expected'] == 1360 and result['lost'] == result['route_lost'] == 0 and
                not result['missing_layers'], 'DeepSeek recorder evidence no longer verifies complete routes')
        self.result['deepseek_trace'] = result
        self.progress('deepseek-trace-checked', 'Recomputed all 1,360 DeepSeek route events and verified zero recorded loss.', [name])

    def granite(self):
        fixture = 'granite-score-02/fixture-evidence.json'
        evidence = json.loads(self.read(fixture))
        cases, sources = {}, [fixture]
        require(evidence['stage_outcome'] == 'pass' and evidence['s6_zero_loss'] is False, 'Granite fixture verdict or loss changed')
        for case in ('C1', 'C2'):
            name = f'granite-score-02/S6/{case}/events.jsonl'
            result = trace(self.read(name), 24)
            expected = evidence['s6_configurations'][case]
            require((result['written'], result['expected'], result['lost']) ==
                    (expected['records'], expected['expected_records'], expected['lost']) and
                    result['route_lost'] == 1 and result['missing_layers'] == {0: [23]}, 'Granite route loss does not match the published fixture')
            cases[case] = result
            sources.append(name)
        self.result['granite_fixture'] = cases
        self.progress('granite-traces-checked', 'Verified Granite S6 retained 1,151 of 1,152 events in each configuration, with one accounted loss each.', sources)

    def finish(self):
        name = 'recorder-evidence-verification.json'
        content = json.dumps(dict(schema='spark-live-recorder-verification/1', pinned_artifacts=PINS, **self.result), indent=2) + '\n'
        self.destination.put_artifact(self.task_id, name, content.encode(), 'application/json', None)
        self.progress('verification-complete', 'Verification complete. DeepSeek was loss-free and the separate Granite fixture recorded one loss per configuration.', [name])


def run(home, task_id):
    os.nice(19)
    available = os.sched_getaffinity(0)
    if cpus := available & set(range(12, 20)):
        os.sched_setaffinity(0, cpus)
    with Store(home) as destination:
        task = destination.get_task(task_id)
        require(valid_template(task), 'Unapproved native evidence task')
        controller = Controller(home=home, store=destination)
        with controller._lock(), Store(home.parent / 'star-observability_event_recorder') as source:
            transcript = home / 'sessions' / (task_id + '.jsonl')
            transcript.parent.mkdir(exist_ok=True)
            state = controller._load(task_id)
            require(state['started'] is None, 'The evidence walkthrough already started')
            state.update(started=time.time(), tick=time.time(), active_s=0)
            checks = RecorderVerification(source, destination, task_id, transcript)
            stages = (
                ('Verify published recorder report', checks.report_pin), ('Check capped DeepSeek output parity', checks.parity),
                ('Recompute the DeepSeek trace', checks.deepseek), ('Recompute the Granite fixture traces', checks.granite),
                ('Publish the verification evidence', checks.finish),
            )
            started = time.monotonic()
            try:
                for index, (label, check) in enumerate(stages):
                    state['native_step'] = label
                    controller._save(task_id, state)
                    time.sleep(max(0, started + index * STEP_SECONDS - time.monotonic()))
                    check()
            except Exception:
                checks.progress('verification-failed', 'Verification stopped. The retained run log contains the failed check.')
                controller._finish(task_id, state, 'evidence_verification_failed')
                raise
            controller._finish(task_id, state, 'evidence_verified')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('home', type=Path)
    parser.add_argument('task_id')
    args = parser.parse_args()
    run(args.home, args.task_id)
