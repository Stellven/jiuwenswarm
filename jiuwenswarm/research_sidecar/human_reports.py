"""Rebuild human-reviewed campaign reports from retained observations only."""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from .evidence import canonical


REVIEW_FIELDS = ('Assessment', 'Evidence references', 'Review notes')
MAX_RECORD_BYTES = 32 * 1024 * 1024


def _read(path):
    if Path(path).is_symlink():
        raise ValueError('Symlink report input denied')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_RECORD_BYTES:
            raise ValueError('Report input must be a bounded regular file')
        return stream.read(MAX_RECORD_BYTES + 1)


def _publish(root, name, raw):
    path = root / name
    if path.exists() or path.is_symlink():
        _read(path)  # Refuse links and foreign file types before replacement.
    fd, temporary = tempfile.mkstemp(prefix='.report-', dir=root)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name == 'posix':
            directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _cell(value):
    if value is None:
        return 'unavailable'
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).replace('|', '\\|').replace('\r', ' ').replace('\n', ' ')


def _csv_cell(value):
    text = '' if value is None else str(value)
    # External task text must not turn a CSV review into a spreadsheet command.
    return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text


def _artifact_link(run_path, artifact):
    from urllib.parse import quote
    from .evidence import relative
    raw = artifact.get('path', '')
    relative(raw)
    return quote((run_path / raw).as_posix(), safe='/.-_')


def build_human_reports(campaign_dir):
    """No scoring, model call or task execution occurs during a report rebuild.

    Human edits within the three marked review blocks survive rebuilding.
    Unrecognized existing reports are refused rather than overwritten.
    """
    source = Path(campaign_dir)
    if any(path.is_symlink() for path in (source, *source.parents)):
        raise ValueError('Symlink campaign directory denied')
    root = source.resolve(strict=True)
    campaign = json.loads(_read(root / 'campaign.json'))
    records = []
    runs = root / 'runs'
    if runs.is_symlink():
        raise ValueError('Symlink runs directory denied')
    for path in sorted(runs.glob('*/run_record.json')):
        if path.parent.is_symlink():
            raise ValueError('Symlink run directory denied')
        record = json.loads(_read(path))
        record['_report_path'] = path.parent.relative_to(root).as_posix()
        records.append(record)
    reviews = {}
    previous = root / 'report.md'
    if previous.exists() or previous.is_symlink():
        text = _read(previous).decode('utf-8').replace('\r\n', '\n')
        if not text.startswith('<!-- ai4r-human-report:1 -->\n'):
            raise ValueError('Existing report is not owned by this report format')
        expression = r'<!-- review:([a-zA-Z0-9_.-]+):(assessment|evidence_references|review_notes) -->\n(.*?)<!-- /review -->'
        for ident, field, content in re.findall(expression, text, re.S):
            if (ident, field) in reviews:
                raise ValueError('Duplicate human review block')
            reviews[(ident, field)] = content
    report = {'schema_version': 'sequential-human-report:1',
              'campaign': campaign, 'runs': records, 'assessment': None,
              'review_policy': 'Human assessment only; execution states are not correctness scores.'}
    lines = ['<!-- ai4r-human-report:1 -->', '# Campaign observations', '',
             'Execution and collection states describe infrastructure, not research correctness.', '',
             '## Inputs and Setup', '', 'Campaign: ' + _cell(campaign.get('campaign_id', root.name)), '',
             '| Case | Repeat | App run | Execution | Collection |', '| --- | ---: | --- | --- | --- |']
    columns = ('case_id', 'repeat_index', 'run_id', 'request_id', 'app_run_id',
               'execution_state', 'collection_state', 'created_at', 'submitted_at',
               'ended_at', 'artifact_count', 'errors', 'assessment', 'evidence_references', 'review_notes')
    matrix = io.StringIO(newline='')
    writer = csv.DictWriter(matrix, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    observed_ids = set()
    for record in records:
        ident = record['run_id']
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+', ident) or ident in observed_ids:
            raise ValueError('Unsafe or duplicate report run identity')
        observed_ids.add(ident)
        lines.append('| ' + ' | '.join(_cell(record.get(key)) for key in
                     ('case_id', 'repeat_index', 'app_run_id', 'execution_state', 'collection_state')) + ' |')
        row = {key: record.get(key) for key in columns}
        row['artifact_count'] = len(record.get('artifacts', []))
        row['errors'] = json.dumps(record.get('errors', []), ensure_ascii=False)
        for field in ('assessment', 'evidence_references', 'review_notes'):
            row[field] = reviews.get((ident, field), '').strip()
        writer.writerow({key: _csv_cell(value) for key, value in row.items()})
    lines += ['', '## Actual Output and Observations', '']
    for record in records:
        ident = record['run_id']
        lines += ['### ' + _cell(record['case_id']) + ' / repeat ' + _cell(record['repeat_index']), '',
                  'Request: ' + _cell(record.get('request_id')), '', 'Task:', '', str(record.get('task', '')), '',
                  'Inputs and setup:', '', '```json',
                  json.dumps({'inputs': record.get('inputs', []), 'setup': record.get('setup', []),
                              'limits': record.get('limits', {})}, ensure_ascii=False, indent=2), '```', '',
                  'Execution: ' + _cell(record.get('execution_state')) + '; collection: '
                  + _cell(record.get('collection_state')) + '.', '',
                  '[Saved run record](' + record['_report_path'] + '/run_record.json)', '']
        for artifact in record.get('artifacts', []):
            link = _artifact_link(Path(record['_report_path']), artifact)
            lines.append('- [Artifact](' + link + ') — SHA-256: ' + _cell(artifact.get('sha256'))
                         + '; bytes: ' + _cell(artifact.get('size')))
        lines += ['', 'Available observations:', '', '```json',
                  json.dumps(record.get('observations', {}), ensure_ascii=False, indent=2), '```', '',
                  'Errors:', '', '```json', json.dumps(record.get('errors', []), ensure_ascii=False, indent=2), '```', '']
        for heading in REVIEW_FIELDS:
            field = heading.lower().replace(' ', '_')
            content = reviews.get((ident, field), '\n')
            lines += ['#### ' + heading, '', '<!-- review:' + ident + ':' + field + ' -->',
                      content.rstrip('\n'), '<!-- /review -->', '']
    # Preserve annotations for any temporarily missing record instead of deleting them.
    if any(ident not in observed_ids for ident, _ in reviews):
        raise ValueError('A reviewed record is missing; report replacement refused')
    report['reviews'] = {ident: {field: reviews.get((ident, field), '').strip()
                                for field in ('assessment', 'evidence_references', 'review_notes')}
                         for ident in sorted(observed_ids)}
    _publish(root, 'report.json', canonical(report))
    _publish(root, 'results.csv', matrix.getvalue().encode('utf-8-sig'))
    _publish(root, 'report.md', ('\n'.join(lines) + '\n').encode('utf-8'))
    return {name: str(root / name) for name in ('report.json', 'results.csv', 'report.md')}
