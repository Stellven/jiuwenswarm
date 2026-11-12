"""Read-only, sanitized evidence bundles. No job reconciliation or Store initialization."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone

from .store import TABLES, NotFound

LIMIT = 50 * 1024 * 1024
ROOT = Path(__file__).resolve().parent
from .redact import SECRET_PATTERNS, scrub_bytes, sanitize
from .config import EXPORT_TIMEOUT


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(sanitize(value), indent=2, ensure_ascii=False, sort_keys=True) + '\n').encode()


def snapshot(home, task_id):
    # mode=ro deliberately avoids Store.__init__ (DDL and WAL configuration).
    with closing(sqlite3.connect((home / 'factory.sqlite').as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        result = {}
        for table in TABLES:
            columns = {r['name'] for r in db.execute(f'PRAGMA table_info({table})') if r['type'] == 'JSON'}
            records = []
            for row in db.execute(f'SELECT * FROM {table} WHERE task_id=?', (task_id,)):
                record = dict(row)
                for key in columns:
                    record[key] = json.loads(record[key]) if record[key] is not None else None
                records.append(record)
            result[table] = sorted(records, key=lambda r: (r.get('rev', 0), r.get('created', 0), str(r)))
        if not result['tasks']:
            raise NotFound('Task not found')
        result['events'] = [dict(r) for r in db.execute('SELECT * FROM evidence WHERE task_id=? ORDER BY cursor', (task_id,))]
        for event in result['events']:
            event['record'] = json.loads(event['record'])
        return result


def command(argv):
    try:
        proc = subprocess.run(argv, capture_output=True, stdin=subprocess.DEVNULL, timeout=EXPORT_TIMEOUT,
                              env=dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0'))
        if proc.returncode:
            return {'available': False, 'error': scrub_bytes(proc.stderr).decode(errors='replace')[:1000]}
        return {'available': True, 'stdout': proc.stdout.decode(errors='replace')}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'available': False, 'error': scrub_bytes(str(exc).encode()).decode()}


def scan(directory):
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('Bundle contains symlink: ' + str(path.relative_to(directory)))
        if path.is_file() and any(p.search(path.read_bytes()) for p in SECRET_PATTERNS):
            # Never include the matched value in an error.
            raise ValueError('Secrets scan failed: ' + str(path.relative_to(directory)))


def verify(directory):
    directory = Path(directory).resolve()
    scan(directory)
    manifest = json.loads((directory / 'MANIFEST.json').read_text())
    actual = {p.relative_to(directory).as_posix(): sha(p.read_bytes())
              for p in directory.rglob('*') if p.is_file() and p != directory / 'MANIFEST.json'}
    if actual != manifest:
        raise ValueError('Manifest paths or SHA256 hashes differ')
    return len(actual)


def export_task(task_id, out, home=None, extra_files=()):
    home = Path(home or os.environ.get('FACTORY_HOME', '~/.jiuwenswarm-factory')).expanduser().resolve()
    out = Path(out).resolve()
    if out == home or out.is_relative_to(home):
        raise ValueError('Export destination must be outside factory home')
    if out.exists():
        raise ValueError('Export destination already exists')
    records = snapshot(home, task_id)
    task = records['tasks'][0]
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.export-', dir=out.parent))
    omissions, artifacts, images, sources, builds = [], [], [], [], []

    def write(name, data):
        path = stage / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(scrub_bytes(data))
        return name

    def record(name, value):
        return write(name, json_bytes(value))

    def copy_blob(path, name=None, expected=None):
        if path.stat().st_size > LIMIT:
            omissions.append({'source': str(path), 'size': path.stat().st_size, 'reason': 'over_50_MiB', 'sha256': expected})
            return None
        data = path.read_bytes()
        if expected and sha(data) != expected:
            raise ValueError('Artifact digest mismatch')
        clean = scrub_bytes(data)
        try:
            parsed = json.loads(data)
            sanitized = sanitize(parsed)
            if sanitized != parsed:
                clean = json_bytes(sanitized)
        except (ValueError, UnicodeDecodeError):
            pass
        return write(name or 'artifacts/' + sha(clean), clean)

    try:
        for table, values in records.items():
            record('records/' + table + '.json', values)
        for item in records['artifacts']:
            path = (home / item['location']).resolve()
            if not path.is_relative_to(home / 'artifacts'):
                raise ValueError('Artifact location escapes artifact root')
            if path.stat().st_size != item['size']:
                raise ValueError('Artifact size mismatch')
            name = copy_blob(path, expected=item['sha256'])
            artifacts.append(dict(item, exported_path=name,
                                  exported_sha256=sha((stage / name).read_bytes()) if name else None))
        record('artifacts.json', artifacts)
        from .telemetry import read_events
        write('telemetry.jsonl', ''.join(json.dumps(sanitize(e), ensure_ascii=False) + '\n'
              for e in read_events(home, task_id)).encode())
        transcript = (home / 'sessions' / (task_id + '.jsonl')).resolve()
        if not transcript.is_relative_to(home / 'sessions'):
            raise ValueError('Session path escapes sessions root')
        if transcript.is_file():
            # Parse each event so sensitive JSON fields are scrubbed too.
            lines = []
            for line in transcript.read_text().splitlines():
                if line.strip():
                    lines.append(json.dumps(sanitize(json.loads(line)), ensure_ascii=False))
            write('session.jsonl', ('\n'.join(lines) + '\n').encode())
        else:
            omissions.append({'source': 'session.jsonl', 'reason': 'no agent session (operator task or unavailable)'})
        releases = {}
        for capsule in sorted((ROOT / 'ccs').iterdir()):
            if not capsule.is_dir():
                continue
            files = {p.relative_to(capsule).as_posix(): sha(p.read_bytes()) for p in sorted(capsule.rglob('*'))
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
            # Tree digest = SHA256 of sorted path<NUL>file-sha256<LF> entries.
            digest = sha(''.join(f'{p}\0{h}\n' for p, h in files.items()).encode())
            releases[capsule.name] = dict(sha256=digest, files=files)
            for relative in files:
                copy_blob(capsule / relative, 'capsules/' + capsule.name + '/' + relative)
        record('capsule-releases.json', {'identity_scope': 'export-time checkout; not an attestation of historical loaded bytes',
                                        'algorithm': 'sha256(sorted relative-path + NUL + file-sha256 + LF); excludes __pycache__ and .pyc', 'capsules': releases})
        contract_ids = {v['contract_id'] for v in records['evaluations']}
        if task.get('contract_id'):
            contract_ids.add(task['contract_id'])
        for cid in sorted(contract_ids):
            from .contract import load
            contract = load(cid)
            copy_blob(contract.path, 'contracts/' + contract.path.name)
        for attempt in records['attempts']:
            if attempt['kind'] != 'build':
                continue
            aid = attempt['attempt_id']
            source = attempt['request'].get('source', {})
            commit = source.get('commit')
            if source.get('path') and commit:
                base = ['git', '-C', source['path']]
                log = command(base + ['log', '-3', '--format=%H %T %P %s'])
                patch = command(base + ['show', '--format=fuller', '--no-ext-diff', commit, '--'])
                record('source/' + aid + '.json', dict(attempt_id=aid, source=source, log=log,
                       integration_diff_available=patch['available'], error=patch.get('error')))
                if patch['available']:
                    write('source/' + aid + '.diff', patch['stdout'].encode())
                sources.append(dict(attempt_id=aid, commit=commit))
            build_item = next((a for a in artifacts if a['artifact_id'] == aid + ':build-record'), None)
            build = {}
            if build_item and build_item['exported_path']:
                build = json.loads((stage / build_item['exported_path']).read_bytes())
                record('builds/' + aid + '/build-record.json', build)
            # Capture already-produced worker outputs; never run/reconcile a job.
            build_root = home / 'builds' / aid
            if build_root.is_dir():
                for path in sorted(build_root.rglob('*')):
                    if path.is_file() and not path.is_symlink() and 'build' not in path.relative_to(build_root).parts:
                        archive = build.get('archive') or {}
                        digest = archive.get('sha256') if path.name == archive.get('path') else None
                        copy_blob(path, 'builds/' + aid + '/worker/' + path.relative_to(build_root).as_posix(), expected=digest)
            image = build.get('image') or {}
            if image.get('Id'):
                inspected = command(['docker', 'image', 'inspect', image['Id']])
                identity = dict(attempt_id=aid, evidence_id=aid + ':build-record',
                                provenance='docker image inspect' if inspected['available'] else 'build record only',
                                inspect_error=inspected.get('error'))
                if inspected['available']:
                    row = json.loads(inspected['stdout'])[0]
                    identity['image'] = {k: row.get(k) for k in ('Id', 'Architecture', 'Os', 'RepoTags')}
                    identity['image']['Labels'] = (row.get('Config') or {}).get('Labels')
                else:
                    identity['image'] = image
                    identity['labels'] = None
                    identity['labels_note'] = 'Unavailable without Docker access; build record does not capture image labels'
                images.append(identity)
            builds.append(dict(attempt_id=aid, state=attempt['state'], build_record=build_item))
        record('image-identity.json', images)
        for extra in extra_files:
            path = Path(extra)
            copy_blob(path, path.name)
        record('omissions.json', omissions)
        record('export.json', dict(task_id=task_id, exported_at=datetime.now(timezone.utc).isoformat(),
               snapshot_cursor=task['evidence_cursor'], factory_git_head=command(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']),
               artifact_policy='50 MiB limit; sanitized copies may have a different SHA256; artifacts.json maps original identities',
               read_only=True))
        lines = [f'# Evidence chain: {task_id}', '',
                 'Read-only snapshot; missing links mean not demonstrated. Artifact IDs map to bundled bytes in [artifacts.json](artifacts.json).', '',
                 '| Component | Integration commit | Build attempt | Image ID | Admission | Lab run | Evaluation |',
                 '|---|---|---|---|---|---|---|']
        for build in builds:
            aid = build['attempt_id']
            source = next((s['commit'] for s in sources if s['attempt_id'] == aid), 'unavailable')
            image = next((i['image'].get('Id') for i in images if i['attempt_id'] == aid), 'not recorded')
            labs = [a for a in records['attempts'] if a['kind'] == 'lab' and a['request'].get('admission', {}).get('build_attempt_id') == aid]
            for lab in labs or [None]:
                admission = lab['request']['admission']['admission_id'] if lab else 'not recorded'
                lid = lab['attempt_id'] if lab else 'not recorded'
                evals = [e['eval_id'] for e in records['evaluations'] if e['eval_id'].startswith(lid + ':')]
                build_evidence = aid + ':build-record' if build['build_record'] else 'build record not present'
                source_link = f'{source} ([diff](source/{aid}.diff))' if (stage / f'source/{aid}.diff').is_file() else source
                lines.append(f"| {task.get('component_cc') or 'not recorded; capsules bundled separately'} | {source_link} | {aid} ({build['state']}); {build_evidence} | {image} | {admission} | {lid} | {', '.join(evals) or 'not recorded'} |")
        if not builds:
            lines.append('| not recorded | not recorded | not recorded | not recorded | not recorded | not recorded | not recorded |')
        lines += ['', '## Evidence records', '']
        for table, values in records.items():
            lines.append(f'- [{table}](records/{table}.json): {len(values)} records')
            if table in {'decisions', 'observations', 'evaluations'}:
                for value in values:
                    key = TABLES[table][0]
                    lines.append(f"  - `{value[key]}`" + (f" rev {value['rev']}" if 'rev' in value else ''))
        lines += ['', '## Limits', '',
                  'Capsule hashes describe the export-time source tree. Git log describes the current owned checkout; each integration diff names the recorded build commit.',
                  'Image identity provenance and Docker access errors: [image-identity.json](image-identity.json).',
                  'Skipped large files and absent session: [omissions.json](omissions.json). No absent chain link is inferred.']
        write('INDEX.md', ('\n'.join(lines) + '\n').encode())
        scan(stage)
        manifest = {p.relative_to(stage).as_posix(): sha(p.read_bytes()) for p in sorted(stage.rglob('*')) if p.is_file()}
        record('MANIFEST.json', manifest)
        verify(stage)
        stage.rename(out)
        return out
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task_id', nargs='?')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--home', type=Path)
    parser.add_argument('--extra-file', type=Path, action='append', default=[])
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.verify:
            print(f'Verified {verify(args.verify)} files; secrets scan clean')
        elif args.task_id and args.out:
            print(export_task(args.task_id, args.out, args.home, args.extra_file))
        else:
            parser.error('provide TASK --out DIR, or --verify DIR')
    except (ValueError, OSError, sqlite3.Error, NotFound) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
