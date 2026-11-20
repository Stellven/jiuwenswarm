#!/usr/bin/env python3
"""Attach a portable report snapshot and export the existing native benchmark task."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
from pathlib import Path
import re
import tempfile
from urllib.parse import unquote, urlsplit

from jiuwenswarm.factory.export import LIMIT, export_task, json_bytes, verify
from jiuwenswarm.factory.redact import sanitize, scrub_bytes
from jiuwenswarm.factory.store import Store

LINK = re.compile(r'!?\[[^\]\n]*\]\((?P<uri><[^>\n]+>|[^()\s]+)(?:\s+"[^"\n]*")?\)')
REFERENCE = re.compile(r'^\[[^\]\n]+\]:\s*(?P<uri><[^>\n]+>|\S+)(?:\s+"[^"\n]*")?\s*$', re.MULTILINE)
DENIED = {'.codex', '.ssh', '.env', 'auth.json', 'credentials.json', 'id_rsa', 'id_ed25519'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def map_links(text, mapper):
    """Handle the report's inline/reference Markdown links, leaving code fences alone."""
    def replace(match):
        raw = match['uri']
        uri = raw[1:-1] if raw.startswith('<') else raw
        replacement = mapper(uri)
        if raw.startswith('<'):
            replacement = '<' + replacement + '>'
        start, end = match.span('uri')
        return match.group()[:start - match.start()] + replacement + match.group()[end - match.start():]
    output = []
    fence = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token[0]
            elif token[0] == fence:
                fence = None
            output.append(line)
        else:
            output.append(line if fence else REFERENCE.sub(replace, LINK.sub(replace, line)))
    return ''.join(output)


def local_target(uri, report, base):
    parsed = urlsplit(uri)
    if not parsed.path and parsed.fragment and not parsed.scheme:
        return None, parsed.fragment
    if parsed.scheme not in ('', 'file') or parsed.netloc not in ('', 'localhost') or parsed.query:
        raise ValueError('Citation must name local evidence, without queries: ' + uri)
    path = Path(unquote(parsed.path)).expanduser()
    if not path.is_absolute():
        path = report.parent / path
    if (any(part.lower() in DENIED or part.lower().startswith('.env') for part in path.parts)
            or path.suffix.lower() in ('.pem', '.key')
            or any(p.is_symlink() for p in (path, *path.parents))):
        raise ValueError('Credential/symlink citation refused: ' + uri)
    path = path.resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise ValueError('Citation is missing or outside the evidence root: ' + uri)
    if path.stat().st_size > LIMIT:
        raise ValueError('Citation exceeds native export size limit: ' + uri)
    return path, parsed.fragment


def native_bytes(data):
    """Predict native copy_blob's sanitized address; validate against artifacts.json after export."""
    clean = scrub_bytes(data)
    try:
        parsed = json.loads(data)
        sanitized = sanitize(parsed)
        if sanitized != parsed:
            clean = json_bytes(sanitized)
    except (ValueError, UnicodeDecodeError):
        pass
    return scrub_bytes(clean)


def publish(report, base, status='draft', out=None, home=None, task_id='spark-direct-benchmarks-20261120'):
    if status not in ('draft', 'final'):
        raise ValueError('Publication status must be draft or final')
    base = Path(base).expanduser().resolve()
    report, _ = local_target(str(Path(report).expanduser().absolute()), Path(report), base)
    original = report.read_bytes()
    citations, snapshots = {}, {}

    def freeze(uri):
        path, fragment = local_target(uri, report, base)
        if path is None:
            return uri
        if path not in snapshots:
            data = path.read_bytes()
            digest = sha(data)
            clean_sha = sha(native_bytes(data))
            snapshots[path] = dict(data=data, artifact_id='source:' + path.relative_to(base).as_posix() + '@sha256:' + digest,
                                   sha256=digest, exported_path='artifacts/' + clean_sha, exported_sha256=clean_sha)
        source = snapshots[path]
        target = source['exported_path'] + ('#' + fragment if fragment else '')
        citations[uri] = dict(source_uri=uri, source_path=path.relative_to(base).as_posix(),
                              artifact_id=source['artifact_id'], sha256=source['sha256'],
                              exported_path=source['exported_path'], exported_sha256=source['exported_sha256'])
        return target

    portable = map_links(original.decode('utf-8'), freeze)
    label = 'DRAFT SNAPSHOT' if status == 'draft' else 'FINAL REPORT SNAPSHOT'
    portable = ('> ' + label + '\n\n' + portable).encode()
    publication_id = 'spark-report-' + status + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    root = base / 'factory-runs'
    home = Path(home).expanduser().absolute() if home else root / 'spark-direct-benchmarks'
    out = Path(out).expanduser().absolute() if out else root / 'exports' / publication_id
    if not (home / 'factory.sqlite').is_file():
        raise ValueError('Existing benchmark home/task required; publication never creates a report-only production task')
    if out.exists():
        raise ValueError('Publication output must be new; prior snapshots are preserved')
    if not home.resolve().is_relative_to(root.resolve()) or not out.resolve().is_relative_to(root.resolve()):
        raise ValueError('Publication home/output must be discoverable beneath factory-runs')
    citation_map = dict(schema='spark-report-publication/1', status=status, source_report_sha256=sha(original),
                        direct_local_citations=list(citations.values()),
                        scope='New imports are the root report and its direct local citations. The export retains the existing benchmark task and receipts; cited source documents retain their original bytes under native sanitization.')
    with Store(home) as store:
        store.get_task(task_id)
        refs = []
        for path, item in snapshots.items():
            store.put_artifact(task_id, item['artifact_id'], item['data'],
                               mimetypes.guess_type(path.name)[0] or 'text/plain', None)
            refs.append(item['artifact_id'])
        for name, data in [('report-original.md', original), ('report.md', portable), ('citation-map.json', json_bytes(citation_map))]:
            identity = 'source:publication/' + name + '@sha256:' + sha(data)
            store.put_artifact(task_id, identity, data, 'application/json' if name.endswith('.json') else 'text/markdown', None)
            refs.append(identity)
        store.append_observation(task_id, dict(kind='report_publication', source_artifacts=refs,
            values=dict(citation_map, message=f'{status.upper()} report and {len(snapshots)} directly cited local files frozen',
                        report_artifact_id=refs[-2], publication_id=publication_id),
            limitations='Operator publication only. No new model run, measurement, implementation or agent result is inferred.'))
    with tempfile.TemporaryDirectory(prefix='spark-report-publication-') as temporary:
        readable = Path(temporary) / 'report.md'
        readable.write_bytes(portable)
        mapping = Path(temporary) / 'citation-map.json'
        mapping.write_bytes(json_bytes(citation_map))
        # Export the real benchmark task, retaining its iterations, measurements
        # and all recorded underlying receipts alongside the readable report.
        export_task(task_id, out, home=home, extra_files=[readable, mapping])
    exported = {item['artifact_id']: item for item in json.loads((out / 'artifacts.json').read_text())}
    for item in snapshots.values():
        actual = exported[item['artifact_id']]
        if (actual['sha256'], actual['exported_path'], actual['exported_sha256']) != (
                item['sha256'], item['exported_path'], item['exported_sha256']):
            raise ValueError('Native citation export differs from the frozen mapping')
    target_count = 0

    def check(uri):
        nonlocal target_count
        parsed = urlsplit(uri)
        if not parsed.path and parsed.fragment:
            return uri
        target = (out / unquote(parsed.path)).resolve()
        if parsed.scheme or parsed.netloc or parsed.query or not target.is_relative_to(out.resolve()) or not target.is_file():
            raise ValueError('Portable report has an unresolved citation: ' + uri)
        target_count += 1
        return uri

    root_bytes = (out / 'report.md').read_bytes()
    if root_bytes != native_bytes(portable):
        raise ValueError('Readable report differs from the native sanitized snapshot')
    map_links(root_bytes.decode('utf-8'), check)
    count = verify(out)
    return dict(status=status, task_id=task_id, publication_id=publication_id, home=str(home), export=str(out),
                source_report_sha256=sha(original), report_sha256=sha(root_bytes),
                citation_count=len(citations), verified_link_targets=target_count,
                verified_manifest_files=count, manifest_sha256=sha((out / 'MANIFEST.json').read_bytes()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=Path.home() / 'predemo-spark')
    parser.add_argument('--report', type=Path, default=Path.home() / 'predemo-spark/report.md')
    parser.add_argument('--status', choices=('draft', 'final'), default='draft')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--home', type=Path)
    parser.add_argument('--task-id', default='spark-direct-benchmarks-20261120')
    args = parser.parse_args()
    print(json.dumps(publish(args.report, args.base, args.status, args.out, args.home, args.task_id), indent=2))


if __name__ == '__main__':
    main()
