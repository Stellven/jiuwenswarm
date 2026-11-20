"""Build curated demo replays from real factory records.

A curated replay SELECTS and ORDERS records that already exist: native store
rows (tasks, decisions, observations, attempts), artifact bytes from factory
homes, sealed capsule release files, session transcripts and OPS lab files
(ledger, receipts, reports). Nothing is invented:

* every copied file keeps its original bytes, so its sha256 equals the source
  file's sha256 (checked on copy and recorded in provenance.json);
* every record row is copied verbatim from the home's factory.sqlite;
* every step names the records and files it shows, with source home, task id
  or OPS path; the only new text is the presentation title, the one-sentence
  presenter line ("say") and file display names, all labelled as such;
* quotes are verbatim lines of a bundled file, with their line numbers.

The output is an ordinary export bundle (records/, MANIFEST.json, ...), so the
web UI lists and replays it. replay.json adds the step order.

    python -m scripts.spark.build_demo_replays \
        --base /home/user2/predemo-spark --out /home/user2/predemo-spark/factory-runs/exports
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile

from jiuwenswarm.factory.redact import SECRET_PATTERNS

SCHEMA = 'factory.curated-replay/1'
TABLES = ('decisions', 'observations', 'attempts', 'evaluations', 'artifacts', 'uploads')
KEYS = {'decisions': 'decision_id', 'observations': 'obs_id', 'attempts': 'attempt_id',
        'evaluations': 'eval_id', 'artifacts': 'artifact_id', 'uploads': 'upload_id'}
JSON_COLUMNS = {'constraints', 'allowed_effects', 'target', 'budget', 'evidence_ids', 'observations', 'action',
                'source_artifacts', 'values', 'error', 'host_run', 'request', 'owner', 'resources', 'result_refs',
                'history', 'contract', 'inputs', 'initial_run_config', 'source', 'operator_labels'}

HOME = 'star-expert_weight_cache-residency-01'
PLAN = 'spark-cache-residency-plan-01'
DO = 'spark-cache-residency-do-01'
BUILD = '32b595d1a67b489eb2fc8bc12ed985d5'
CAPSULE_V13 = 'f85f3e6200ba4f1ecccc6d5c4bc1f3cb74daf76f1d0e7e63be4885825f838a4d'
RELEASE = f'ccstore/releases/{CAPSULE_V13}'


class Omitted(Exception):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def art(task, artifact_id, label, key=None):
    return dict(kind='artifact', home=HOME, task=task, id=artifact_id, label=label, key=key)


def home_file(rel, label, key=None, home=HOME):
    return dict(kind='home_file', home=home, path=rel, label=label, key=key)


def ops(rel, label, key=None):
    return dict(kind='ops', path=rel, label=label, key=key)


def excerpt(name, source, ranges, label, key=None):
    return dict(kind='excerpt', name=name, source=source, ranges=ranges, label=label, key=key)


def rec(table, task, record_id, home=HOME):
    return dict(table=table, home=home, task=task, id=record_id)


SESSION = home_file(f'sessions/{DO}.jsonl', 'Session transcript · spark-cache-residency-do-01 (full)')
LEDGER = ops('LEDGER.jsonl', 'Measurement ledger · OPS/LEDGER.jsonl (full)')
REPORT_V3 = 'iterations/spark-p4-cache60-build-overlap/report-v3.md'

# Replay 1: the expert weight cache builder, capsule v1.3 (profile seeding via
# mmap and the page cache), one change from contract to the measured 60 GiB
# quiet A-B-B-A result. One build (32b595d1, commit ad2130b0) throughout.
REPLAY_1 = dict(
    folder='curated-replay-1-expert-weight-cache-v1.3',
    title='Replay 1: Expert weight cache builder v1.3, one test start to finish',
    primary=(HOME, DO),
    order=1,
    steps=[
        dict(
            title='The task: the contract the factory must satisfy',
            say='The owner gave the factory the star-deepseek-v1 contract and one Capability Capsule in scope, the expert weight cache builder.',
            primary=dict(table='tasks', home=HOME, task=PLAN, id=PLAN),
            records=[rec('tasks', DO, DO), rec('observations', DO, f'{DO}:plan:1')],
            graph=['contract:star-deepseek-v1', f'task:{DO}', 'step:inspect'],
            files=[
                art(DO, 'input-0:star-deepseek-v1.json', 'Task contract · star-deepseek-v1.json',
                    'The pinned contract: model, workload, budget and the capsule slice in scope'),
                art(DO, 'input-1:star-deepseek-v1.md', 'Task contract (readable) · star-deepseek-v1.md',
                    'The same contract in prose'),
                home_file(f'{RELEASE}/bundle/ONTOLOGY.yaml', "Capsule ontology slice · ONTOLOGY.yaml (v1.3)",
                          "The part of the system ontology this capsule may change"),
                ops('DECISIONS.md', 'Owner decisions log · OPS/DECISIONS.md',
                    'Line 20: owner hypothesis prioritized, test source residency'),
            ],
            quotes=[dict(file='ops:DECISIONS.md', lines=[20])],
        ),
        dict(
            title='The plan: the planner reads the reports and picks the change',
            say='The planner read seven prior reports, recorded a read receipt for each, then selected native profile seeding for the cache.',
            primary=dict(table='decisions', home=HOME, task=PLAN, id=f'{PLAN}:decision:2'),
            records=[rec('decisions', PLAN, f'{PLAN}:decision:1'),
                     rec('observations', PLAN, 'cache-planner-complete-reports-read'),
                     rec('observations', PLAN, 'cache-plan-measured-fault-steering')],
            graph=['step:applicability'],
            files=[
                art(DO, 'planner-complete-report-read-receipts.json', 'Planner read receipts · 7 reports',
                    'Proof the planner read every input report in full'),
                art(DO, 'selected-plan-rev2.json', 'Selected plan · spark-cache-residency-plan-01 rev 2',
                    'The plan the DO task was handed'),
                art(PLAN, 'aplus-calibration-fault-io-report.json', 'Report read · A+ calibration fault I/O',
                    'Owner-required input: measured decode fault and read evidence'),
                art(DO, 'incoming-p1-reference-report.md', 'Report read · P1 reference',
                    'Input report: the stock baseline the change must beat'),
                art(PLAN, 'incoming-c1-functional-report-v2.md', 'Report read · C1 functional v2',
                    'Input report: the earlier cache iteration'),
                art(PLAN, 'routing-residency-counterfactual-report.json', 'Report read · routing residency counterfactual',
                    'Input report: how routing changes which expert pages stay resident'),
            ],
        ),
        dict(
            title='The capsule: sealed expert weight cache builder v1.3',
            say='The builder methodology was sealed as release f85f3e62 (cc.yaml, METHOD, verifier) before any code was written.',
            primary=dict(table='observations', home=HOME, task=DO, id='revised-cache-do-source-window'),
            graph=['capsule:engine.build_expert_weight_cache', 'step:applicability'],
            files=[
                art(DO, 'selected-native-capsule-manifest.json', 'Sealed capsule manifest · release f85f3e62 (v1.3)',
                    'File-by-file sha256 of the sealed release the DO task admitted'),
                home_file(f'{RELEASE}/bundle/cc.yaml', 'Capsule · cc.yaml (v1.3)', 'What the capsule declares it builds'),
                home_file(f'{RELEASE}/bundle/METHOD.md', 'Capsule · METHOD.md (v1.3)', 'The builder method the agent follows'),
                home_file(f'{RELEASE}/bundle/VALIDATION.md', 'Capsule · VALIDATION.md (v1.3)', 'How the verifier decides pass or fail'),
                home_file(f'{RELEASE}/bundle/helpers/verify_gate.py', 'Capsule verifier · helpers/verify_gate.py (v1.3)',
                          'The gate check the verifier runs'),
                home_file(f'{RELEASE}/manifest.json', 'Capsule release manifest · ccstore f85f3e62'),
            ],
        ),
        dict(
            title='The code change: JiuwenSwarm writes the cache seeding',
            say='In turn 2 the JiuwenSwarm session applied four source edits through the source workbench, ran the capsule verifier and committed.',
            primary=dict(table='decisions', home=HOME, task=DO, id=f'{DO}:decision:3'),
            records=[rec('decisions', DO, f'{DO}:decision:1'), rec('decisions', DO, f'{DO}:decision:2')],
            graph=['step:integrate'],
            files=[
                art(DO, 'cache-native-profile.diff', 'Diff · expert weight cache native profile seeding (stock 9048bad8 → ad2130b0)',
                    'The actual code change'),
                excerpt('session-do-01-turn2-edits.jsonl', SESSION, [(453, 453), (500, 521), (605, 606)],
                        'Session excerpt · turn 2 edits, verify and localcommit (lines 453, 500-521, 605-606)',
                        'The agent tool calls that wrote and committed the code'),
                art(DO, 'cache-native-authored-edits.json', 'Authored edits · four exact replacements',
                    'The exact replacements the agent authored, with digests'),
                SESSION,
            ],
        ),
        dict(
            title='The sealed source commit ad2130b0',
            say='The change was committed as ad2130b0 on stock 9048bad8 and handed to the build with its static receipt.',
            primary=dict(table='observations', home=HOME, task=DO, id='cache-native-profile-build-handoff'),
            records=[rec('decisions', DO, f'{DO}:decision:4'), rec('decisions', DO, f'{DO}:decision:5'),
                     rec('observations', DO, f'{DO}:plan:2')],
            graph=['step:integrate', 'step:report'],
            files=[
                art(DO, 'cache-native-source-checkpoint.json', 'Source checkpoint · commit ad2130b0',
                    'The sealed commit and its clean tree'),
                art(DO, 'cache-native-profile-static-receipt.json', 'Static verifier receipt · native profile',
                    'Capsule verifier result on the committed diff'),
                art(DO, 'cache-native-profile-verified-native-request.json', 'Build request · verified native',
                    'What the sealed commit handed to the native build'),
            ],
        ),
        dict(
            title='The native build: stock CMake recipe, one pinned binary',
            say='Build 32b595d1 compiled the commit with the stock CMake recipe in 254 s and pinned the binary 6e7fe898.',
            primary=dict(table='observations', home=HOME, task=DO, id=f'{BUILD}:build-result'),
            records=[rec('observations', DO, 'revised-native-cache-build-verified'), rec('attempts', DO, BUILD)],
            graph=['step:candidate-build'],
            files=[
                art(DO, f'{BUILD}:receipt', 'Build receipt · 32b595d1', 'Binary sha256 and build outcome'),
                art(DO, f'{BUILD}:build-record', 'Build record · 32b595d1 (CMake recipe)', 'The exact build recipe'),
                art(DO, 'revised-native-cache-elf-manifest.json', 'ELF manifest · pinned binary and libraries',
                    'sha256 of the binary the lab ran'),
                art(DO, f'{BUILD}:engine-cmake.log', 'CMake log · 32b595d1'),
                art(DO, 'revised-native-cache-readelf.txt', 'readelf · pinned binary'),
            ],
        ),
        dict(
            title='The gate check: off by default, active when switched on',
            say='Static checks show the gate is off by default; with the gate on, the 60 GiB launch logged the activation marker, and output matched stock.',
            primary=dict(table='observations', home=HOME, task=DO, id='native-cache-profile-verifier-direct'),
            records=[rec('observations', DO, 'spark-c3-native-cache:report')],
            graph=['step:candidate-measure'],
            files=[
                art(DO, 'cache-native-source-static-verification.json', 'Static gate checks · env_gate_default_off',
                    'Gate off by default: pass; gate-unset silence: inconclusive'),
                excerpt('c3-60g-activation-marker.log', ops('runs/p4-cache60-c3-pass-2-retry-01/stderr.log', ''), [(8060, 8060)],
                        'Activation marker · 60 GiB C3 launch, stderr line 8060',
                        'Gate on: "active seeds=7432" in the measured launch'),
                ops('iterations/spark-c3-native-cache/pilot/report.md', 'Pilot report · greedy parity vs stock (30 GiB)',
                    'Lines 45-50: greedy output matched stock at every position'),
                ops('runs/p4-cache60-c3-pass-2-retry-01/stderr.log', 'Lab stderr · 60 GiB C3 pass 2 retry (full)'),
            ],
            quotes=[dict(file='ops:runs/p4-cache60-c3-pass-2-retry-01/stderr.log', lines=[8060]),
                    dict(file='ops:iterations/spark-c3-native-cache/pilot/report.md', lines=[45, 47, 48])],
        ),
        dict(
            title='The lab run: quiet A-B-B-A at 60 GiB, capped',
            say='Four fresh capped launches, stock A+ then C3 then C3 then a quiet stock replacement, each with ten matched requests per prompt size.',
            primary=dict(table='file', file='ops:DECISIONS.md', line=53),
            graph=['step:candidate-measure'],
            files=[
                ops('p4/cache-abba-60g.json', 'Lab plan · 60 GiB admitted launches (mmap-seed, ad2130b0)',
                    'Names the four launches and the subject commit ad2130b0'),
                excerpt('ledger-60g-admitted.jsonl', LEDGER, [(676, 743), (778, 811), (976, 1009)],
                        'Ledger rows · 60 GiB admitted launches (lines 676-743, 778-811, 976-1009)',
                        'Request-by-request start and stop records of the four admitted launches'),
                ops('runs/p4-cache60-c3-pass-1-01/result.json', 'Lab receipt · 60 GiB C3 pass 1',
                    'C3 launch result'),
                ops('runs/p4-cache60-aplus-pass-2-quiet-01/result.json', 'Lab receipt · 60 GiB A+ pass 2 (quiet replacement)',
                    'The quiet stock control'),
                ops('p4/cache-abba-60g-quiet-control-amendment.json', 'Amendment · quiet control replacement'),
                ops('p4/cache-abba-60g-amendment.json', 'Amendment · excluded C3 pass 2 (monitor failure)'),
                ops('runs/p4-cache60-aplus-pass-1-01/result.json', 'Lab receipt · 60 GiB A+ pass 1'),
                ops('runs/p4-cache60-c3-pass-2-retry-01/result.json', 'Lab receipt · 60 GiB C3 pass 2 retry'),
                ops('STATUS.md', 'Campaign status log · OPS/STATUS.md (line 208: earlier v2 numbers, superseded by report-v3)'),
                LEDGER,
            ],
            quotes=[dict(file='ops:DECISIONS.md', lines=[43, 53])],
        ),
        dict(
            title='The measured result: first token 27.08 s and 92.07 s sooner',
            say='Against same-budget stock, C3 returned the first token 27.08 s sooner at 512 tokens and 92.07 s sooner at 2048, every one of ten pairs per size faster; the seeded server took about 88 s longer to become ready.',
            primary=dict(table='file', file='ops:DECISIONS.md', line=54),
            graph=['step:report', 'step:accept'],
            files=[
                ops(REPORT_V3, 'Measured result · 60 GiB quiet A-B-B-A report-v3',
                    'Lines 3, 27, 43: 27.08 / 92.07 s saved; lines 94-97: startup cost; lines 108, 110: reads and faults'),
                ops('final-headlines.json', 'Headline table · OPS/final-headlines.json (row c3-60)',
                    'The published headline row cites report-v3 by sha256'),
                ops('iterations/spark-p4-cache60-build-overlap/iteration-v3.json', 'Iteration record · 60 GiB v3',
                    'Machine-readable iteration record behind report-v3'),
                ops('iterations/spark-p4-cache60-build-overlap/analysis-v3.json', 'Analysis · 60 GiB v3'),
            ],
            quotes=[dict(file=f'ops:{REPORT_V3}', lines=[3, 27, 43, 94, 95, 96, 97, 108, 110])],
        ),
    ],
)

REPLAYS = (REPLAY_1,)


def connect(home: Path):
    db = sqlite3.connect((home / 'factory.sqlite').as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return closing(db)


def row(db, table, task, record_id):
    key = 'task_id' if table == 'tasks' else KEYS[table]
    found = db.execute(f'SELECT * FROM {table} WHERE task_id=? AND {key}=?', (task, record_id)).fetchone()
    if not found:
        raise LookupError(f'{table} {record_id} not found for task {task}')
    value = dict(found)
    for column in JSON_COLUMNS & set(value):
        if isinstance(value[column], str):
            value[column] = json.loads(value[column])
    return value


def short_path(home, rel):
    """Bundle path for a home file: short home alias; 64-hex directory names cut to 12 (Windows MAX_PATH)."""
    alias = home.removeprefix('star-expert_weight_cache-').removeprefix('star-')
    parts = rel.split('/')
    parts = [p[:12] if re.fullmatch(r'[0-9a-f]{64}', p) and i < len(parts) - 1 else p for i, p in enumerate(parts)]
    return f'evidence/{alias}/' + '/'.join(parts)


def utc(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


class Builder:
    def __init__(self, base: Path, stage: Path, spec):
        self.base, self.stage, self.spec = base, stage, spec
        self.factory = base / 'factory-runs'
        self.ops = base / 'OPS'
        self.files = {}  # bundle path -> provenance
        self.records = {t: {} for t in ('tasks', *TABLES)}
        self.artifacts = []
        self.homes = set()
        self.omissions = []

    # -- files ------------------------------------------------------------
    def copy(self, source: Path, target: str, provenance: dict, expected=None):
        data = source.read_bytes()
        digest = sha(data)
        if expected and digest != expected:
            raise ValueError(f'sha256 mismatch for {source}')
        if target in self.files:
            return target
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            # Bytes must stay unchanged, so a file that trips the secret scan
            # is left out (and listed) rather than scrubbed.
            self.omissions.append(dict(provenance, sha256=digest, size=len(data),
                                       reason='matches a secret pattern; left out rather than altered'))
            raise Omitted(target)
        path = self.stage / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.files[target] = dict(provenance, sha256=digest, size=len(data))
        return target

    def resolve(self, item):
        """Copy one referenced file; return (bundle path, source path, provenance)."""
        kind = item['kind']
        if kind == 'artifact':
            home = self.factory / item['home']
            with connect(home) as db:
                value = row(db, 'artifacts', item['task'], item['id'])
            self.add_record('artifacts', item['home'], value)
            source = home / value['location']
            target = short_path(item['home'], value['location'])
            provenance = dict(source='factory_home_artifact', source_home=item['home'], task_id=item['task'],
                              artifact_id=item['id'], source_path=value['location'])
            path = self.copy(source, target, provenance, expected=value['sha256'])
            if not any(a['exported_path'] == path and a['artifact_id'] == item['id'] for a in self.artifacts):
                self.artifacts.append(dict(value, exported_path=path, exported_sha256=value['sha256'],
                                           source_home=item['home']))
            self.homes.add(item['home'])
            return path, source
        if kind == 'home_file':
            source = self.factory / item['home'] / item['path']
            target = short_path(item['home'], item['path'])
            self.homes.add(item['home'])
            return self.copy(source, target, dict(source='factory_home_file', source_home=item['home'],
                                                  source_path=item['path'])), source
        if kind == 'ops':
            source = self.ops / item['path']
            return self.copy(source, f"evidence/OPS/{item['path']}",
                             dict(source='ops_file', source_path='OPS/' + item['path'])), source
        if kind == 'excerpt':
            _, source = self.resolve(item['source'])
            lines = source.read_bytes().splitlines(keepends=True)
            picked = b''.join(b''.join(lines[a - 1:b]) for a, b in item['ranges'])
            target = 'excerpts/' + item['name']
            path = self.stage / target
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(picked)
            source_rel = self.bundle_path(item['source'])
            self.files[target] = dict(source='verbatim_excerpt', excerpt_of=source_rel,
                                      excerpt_of_sha256=self.files[source_rel]['sha256'],
                                      line_ranges=[list(r) for r in item['ranges']],
                                      sha256=sha(picked), size=len(picked))
            return target, source
        raise ValueError(kind)

    def bundle_path(self, item):
        if item['kind'] == 'ops':
            return 'evidence/OPS/' + item['path']
        if item['kind'] == 'home_file':
            return short_path(item['home'], item['path'])
        raise ValueError(item['kind'])

    def quote(self, ref, numbers):
        kind, rel = ref.split(':', 1)
        assert kind == 'ops'
        path = self.copy(self.ops / rel, 'evidence/OPS/' + rel, dict(source='ops_file', source_path='OPS/' + rel))
        lines = [line.decode('utf-8', 'replace') for line in (self.stage / path).read_bytes().splitlines()]
        return [dict(path=path, line=n, text=lines[n - 1]) for n in numbers]

    # -- records ----------------------------------------------------------
    def add_record(self, table, home, value):
        key = (value['task_id'], value['task_id'] if table == 'tasks' else value[KEYS[table]])
        self.records[table].setdefault(key, value)
        self.homes.add(home)

    def take(self, ref):
        with connect(self.factory / ref['home']) as db:
            value = row(db, ref['table'], ref['task'], ref['id'])
        self.add_record(ref['table'], ref['home'], value)
        return value

    # -- build ------------------------------------------------------------
    def build(self):
        from jiuwenswarm.factory import story

        home_name, task_id = self.spec['primary']
        with connect(self.factory / home_name) as db:
            primary_task = row(db, 'tasks', task_id, task_id)
            plan_rows = [dict(r) for r in db.execute(
                "SELECT obs_id FROM observations WHERE task_id=? AND kind='taskgraph_patch'", (task_id,))]
        self.add_record('tasks', home_name, primary_task)
        for plan in plan_rows:
            self.take(rec('observations', task_id, plan['obs_id'], home=home_name))
        steps = []
        for number, step in enumerate(self.spec['steps'], 1):
            refs = []
            primary = step['primary']
            if primary['table'] == 'file':
                quote = self.quote(primary['file'], [primary['line']])[0]
                match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))', quote['text'])
                if not match:
                    raise ValueError(f'No timestamp at {primary}')
                created = datetime.fromisoformat(match[1].replace('Z', '+00:00')).timestamp()
                event = dict(id=f"{quote['path']}#L{quote['line']}", kind='ops_record_line',
                             summary=quote['text'], created=created)
                refs.append(dict(table='file', id=f"{quote['path']}#L{quote['line']}", source='OPS/' + primary['file'][4:],
                                 line=primary['line']))
            else:
                value = self.take(primary)
                refs.append(dict(table=primary['table'], id=primary['id'], source_home=primary['home'],
                                 task_id=primary['task']))
                event = self.native_event(story, primary, value)
            for ref in step.get('records', []):
                self.take(ref)
                refs.append(dict(table=ref['table'], id=ref['id'], source_home=ref['home'], task_id=ref['task']))
            key_files, files = [], []
            for item in step['files']:
                try:
                    path, _ = self.resolve(item)
                except Omitted:
                    continue
                files.append(path)
                if item.get('label'):
                    self.files[path]['display_name'] = item['label']
                if item.get('key'):
                    key_files.append(dict(path=path, label=item['label'], why=item['key']))
            quotes = [q for spec in step.get('quotes', []) for q in self.quote(spec['file'], spec['lines'])]
            steps.append(dict(
                step=number, presentation_title=step['title'], presentation_label='Presentation title',
                say=step['say'], say_label='Presenter line (not a record)',
                original_kind=event['kind'], original_summary=event['summary'], created=event['created'],
                created_utc=utc(event['created']), primary_record=event['id'], records=refs,
                files=files, key_files=key_files, quotes=quotes, graph_nodes=step.get('graph', [])))
        for item in steps:
            if not 3 <= len(item['key_files']) <= 6 and item['key_files']:
                raise ValueError(f"Step {item['step']} must flag 3-6 key files; omitted: {[o.get('artifact_id') or o.get('source_path') for o in self.omissions]}")
        self.write(steps, primary_task)

    def native_event(self, story, primary, value):
        event = self._native_event(story, primary, value)
        if primary['table'] == 'observations' and event['summary'] in {value['kind'], ''} | {event['kind']}:
            # The story projection prints only the kind for some observation
            # kinds; show the record's own scalar values instead.
            flat = {}
            for key, item in (value.get('values') or {}).items():
                if isinstance(item, dict):
                    flat.update({f'{key}.{k}': v for k, v in item.items() if isinstance(v, (str, int, float, bool))})
                elif isinstance(item, (str, int, float, bool)):
                    flat[key] = item
            event = dict(event, summary=' · '.join(f'{k} {v}' for k, v in list(flat.items())[:6]))
        if event['kind'] == 'build':
            v = value.get('values') or {}
            exe = v.get('executable') or {}
            event = dict(event, summary=f"{v.get('status')} · {round(v.get('build_wall_seconds') or 0)} s · commit "
                         f"{str(v.get('source_commit'))[:8]} → binary sha256 {str(exe.get('sha256'))[:12]}")
        return event

    def _native_event(self, story, primary, value):
        if primary['table'] == 'tasks':
            return dict(id=value['task_id'], kind='task', summary=value['objective'], created=value['created'])
        with tempfile.TemporaryDirectory() as tmp:
            home = self.factory / primary['home']
            for name in ('factory.sqlite', 'factory.sqlite-wal'):
                if (home / name).exists():
                    shutil.copyfile(home / name, Path(tmp) / name)
            from jiuwenswarm.factory.export import snapshot
            data = snapshot(Path(tmp), primary['task'])
        data['_meta'] = {'turn_ends': []}
        for event in story.build_events(data):
            if event['id'] == primary['id'] or event['id'].startswith(primary['id'] + ':'):
                return event
        raise LookupError(f"No story event for {primary['id']}")

    def write(self, steps, primary_task):
        homes = sorted(self.homes)
        n = len(homes)
        summary = (f"Curated replay: selected real records from {n} factory home{'s' if n != 1 else ''}"
                   f" ({', '.join(homes)}) and the OPS lab records. Step order, presentation titles and presenter"
                   ' lines are curation; every record and file is copied unchanged from its source.')
        dump = lambda name, value: self.write_json(name, value)
        dump('records/tasks.json', [primary_task])
        dump('source-tasks.json', [t for t in self.records['tasks'].values() if t['task_id'] != primary_task['task_id']])
        for table in TABLES:
            dump(f'records/{table}.json', sorted(self.records[table].values(),
                                                  key=lambda r: (r.get('created') or r.get('started') or 0, str(r.get(KEYS[table])))))
        contract = next(a for a in self.artifacts if a['artifact_id'].endswith('star-deepseek-v1.json'))
        self.copy(self.stage / contract['exported_path'], 'contracts/star-deepseek-v1.json',
                  dict(self.files[contract['exported_path']], copy_of=contract['exported_path']))
        dump('artifacts.json', self.artifacts)
        dump('omissions.json', self.omissions)
        replay = dict(schema=SCHEMA, title=self.spec['title'], summary=summary, order=self.spec['order'],
                      primary_task=primary_task['task_id'], source_homes=homes, steps=steps,
                      built_at=datetime.now(timezone.utc).isoformat(),
                      rules=['No invented events or numbers', 'Files keep their original sha256',
                             'Every record and file names its source'])
        dump('replay.json', replay)
        dump('key_files.json', {str(s['step']): s['key_files'] for s in steps})
        dump('provenance.json', dict(
            files=self.files,
            records={t: [dict(task_id=k[0], id=k[1]) for k in rows] for t, rows in self.records.items()},
            source_homes=homes))
        lines = [f"# {self.spec['title']}", '', summary, '']
        for s in steps:
            lines += [f"## Step {s['step']}. {s['presentation_title']}", '',
                      f"*Original kind:* `{s['original_kind']}` · *recorded:* {s['created_utc']} · *primary record:* `{s['primary_record']}`", '',
                      f"> {s['original_summary']}", '', '**Key files**', '']
            lines += [f"- ★ [{k['label']}]({k['path']}): {k['why']}" for k in s['key_files']]
            if s['quotes']:
                lines += ['', '**Verbatim lines**', '']
                lines += [f"- `{q['path']}` line {q['line']}: {q['text'][:300]}" for q in s['quotes']]
            lines.append('')
        (self.stage / 'INDEX.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        manifest = {p.relative_to(self.stage).as_posix(): sha(p.read_bytes())
                    for p in sorted(self.stage.rglob('*')) if p.is_file()}
        dump('MANIFEST.json', manifest)

    def write_json(self, name, value):
        # Same serializer and sanitizer as the native export: record rows come
        # from SQLite, so the bundle's records/*.json are new files.
        from jiuwenswarm.factory.export import json_bytes
        from jiuwenswarm.factory.redact import scrub_bytes
        path = self.stage / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(scrub_bytes(json_bytes(value)))


def build(base: Path, out: Path, spec, replace=False):
    target = out / spec['folder']
    if target.exists():
        if not replace:
            raise ValueError(f'{target} exists; pass --replace')
        shutil.rmtree(target)
    out.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.curated-', dir=out))
    try:
        Builder(base, stage, spec).build()
        from jiuwenswarm.factory.export import verify
        verify(stage)
        stage.rename(target)
        return target
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base', type=Path, required=True, help='Spark data root holding factory-runs/ and OPS/')
    parser.add_argument('--out', type=Path, help='Output folder (default BASE/factory-runs/exports)')
    parser.add_argument('--replace', action='store_true', help='Replace existing curated bundles')
    args = parser.parse_args(argv)
    out = args.out or args.base / 'factory-runs' / 'exports'
    for spec in REPLAYS:
        print(build(args.base.resolve(), out.resolve(), spec, args.replace))


if __name__ == '__main__':
    main()
