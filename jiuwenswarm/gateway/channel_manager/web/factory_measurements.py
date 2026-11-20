"""Read campaign measurements and their paired OPS ledger and result evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Literal

from fastapi import HTTPException

from jiuwenswarm.factory.redact import sanitize

_ARMS = {'A', 'A+', 'C1', 'C2', 'C3', 'C4', 'C5', 'D', 'S'}
_METRICS = ('ttft_s', 'decode_tps', 'peak_memory_bytes', 'inverse_a', 'gap')
_MAX_BYTES = 16 * 1024 * 1024


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _read(path):
    with path.open('rb') as stream:
        data = stream.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise ValueError('Measurement evidence exceeds view limit')
    return data


def _phase(row):
    mark = row.get('measurement_phase', row.get('phase'))
    return 'final' if isinstance(mark, str) and mark.lower() in {'final', 'p4'} else 'reconnaissance'


def _benchmark_row(row):
    return (isinstance(row.get('arm'), str) and row['arm'] in _ARMS
            and row.get('event') in ('request-stop', 'measurement-summary'))


class MeasurementEvidence:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()

    def _rows(self):
        path = self.root / 'LEDGER.jsonl'
        if path.is_symlink():
            raise ValueError('Ledger symlinks are not measurement evidence')
        if not path.is_file():
            return {}
        rows = {}
        for line, raw in enumerate(_read(path).splitlines(), 1):
            try:
                row = json.loads(raw)
            except (ValueError, UnicodeError):
                continue  # A writer can leave a trailing partial line during a read.
            if isinstance(row, dict):
                rows[line] = row
        return rows

    def _result_path(self, row):
        ref = row.get('result_path')
        if not isinstance(ref, str):
            raise ValueError('Missing measurement result path')
        path = Path(ref)
        if not path.is_absolute():
            if path.parts and path.parts[0] == self.root.name:
                path = self.root.parent / path
            else:
                path = self.root / path
        if path.name != 'result.json':
            path /= 'result.json'
        if '..' in path.parts or not path.is_relative_to(self.root / 'runs') or path.resolve() != path:
            raise ValueError('Result is outside the allowed measurement runs')
        return path

    def _evidence(self, line, row):
        try:
            path = self._result_path(row)
            raw = _read(path)
        except FileNotFoundError:
            return {'line': line, 'integrity': 'missing'}, None
        except (OSError, ValueError):
            return {'line': line, 'integrity': 'unavailable'}, None
        digest = hashlib.sha256(raw).hexdigest()
        expected = row.get('result_sha256')
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            result = None
        equivalent = isinstance(result, dict) and result and all(
            key in row and row[key] == value for key, value in result.items()
        )
        # Require independent attestation of the measured fields. A partial
        # result file may otherwise agree vacuously with the ledger row.
        fields = {
            'request-stop': ('arm', 'prompt_tokens', 'prompt_sha256', 'ttft_s', 'decode_tps', 'started',
                             'discard', 'ok', 'usage', 'timings'),
            'measurement-summary': ('arm', 'prompt_tokens', 'prompt_sha256', 'confidence_intervals'),
            'stop': ('peak_memory_bytes', 'scope_verified', 'returncode', 'binary_sha256', 'start', 'stop'),
        }
        consistent = equivalent and all(key in result for key in fields[row['event']])
        if not consistent or (expected is not None and expected != digest):
            status = 'mismatch'
        else:
            status = 'verified' if expected else 'ledger-match'
        source = dict(line=line, path=path.relative_to(self.root).as_posix(), sha256=digest, integrity=status)
        if expected is not None:
            source['expected_sha256'] = expected
        return source, result

    @staticmethod
    def _eligible(row):
        usage = row.get('usage')
        timings = row.get('timings')
        prompt = row.get('prompt_tokens')
        return (row.get('event') == 'request-stop'
                and row.get('ok') is True and row.get('discard') is False
                and row.get('measurement_eligible') is not False
                and type(prompt) is int and prompt > 0
                and isinstance(usage, dict) and usage.get('prompt_tokens') == prompt
                and isinstance(timings, dict) and timings.get('cache_n', 0) == 0
                and _number(row.get('ttft_s')) and row['ttft_s'] > 0)

    @staticmethod
    def _sample(row, source):
        return dict(arm=row['arm'], phase=_phase(row), prompt_tokens=row['prompt_tokens'],
                    prompt_sha256=row['prompt_sha256'], ttft_s=row['ttft_s'],
                    decode_tps=row.get('decode_tps') if _number(row.get('decode_tps')) else None,
                    source=source)

    @staticmethod
    def _intervals(row):
        intervals = row.get('confidence_intervals')
        if not isinstance(intervals, dict):
            return {}
        valid = {}
        for metric in _METRICS:
            at = intervals.get(metric)
            source_lines = at.get('source_lines') if isinstance(at, dict) else None
            if (isinstance(at, dict) and all(_number(at.get(k)) for k in ('low', 'high', 'level'))
                    and at['low'] <= at['high'] and 0 < at['level'] < 1
                    and type(at.get('n')) is int and at['n'] > 0
                    and isinstance(source_lines, list) and source_lines
                    and all(type(line) is int and line > 0 for line in source_lines)
                    and len(set(source_lines)) == len(source_lines)):
                valid[metric] = {key: at[key] for key in ('low', 'high', 'level', 'n', 'source_lines')}
        return valid

    def _scopes(self, rows):
        scopes = {}
        for line, row in rows.items():
            if (row.get('event') == 'stop' and row.get('scope_verified') is True
                    and row.get('returncode') == 0 and _number(row.get('peak_memory_bytes'))
                    and row['peak_memory_bytes'] > 0):
                try:
                    scopes[self._result_path(row).parent] = (line, row)
                except ValueError:
                    continue
        return scopes

    def listing(self):
        rows = self._rows()
        scopes = self._scopes(rows)
        samples, summaries, issues = [], [], {}
        scope_evidence = {}
        seen = set()
        for line, row in rows.items():
            if not _benchmark_row(row) or not isinstance(row.get('prompt_sha256'), str):
                continue
            if not self._eligible(row) and row['event'] != 'measurement-summary':
                continue
            source, _ = self._evidence(line, row)
            if source['integrity'] not in {'verified', 'ledger-match'}:
                issues[line] = source
                continue
            if row['event'] == 'measurement-summary':
                intervals = self._intervals(row)
                if intervals and type(row.get('prompt_tokens')) is int:
                    summaries.append(dict(arm=row['arm'], phase=_phase(row), prompt_tokens=row['prompt_tokens'],
                                          prompt_sha256=row['prompt_sha256'], intervals=intervals, source=source))
                continue
            if source['path'] in seen:
                continue
            seen.add(source['path'])
            sample = self._sample(row, source)
            result = self.root / source['path']
            for parent in result.parent.parents:
                scope = scopes.get(parent)
                if not scope:
                    continue
                scope_line, scope_row = scope
                started, start, stop = row.get('started'), scope_row.get('start'), scope_row.get('stop')
                if (not row.get('binary_sha256') or row['binary_sha256'] != scope_row.get('binary_sha256')
                        or not all(isinstance(stamp, str) for stamp in (started, start, stop))
                        or not start <= started <= stop):
                    continue
                if scope_line not in scope_evidence:
                    scope_evidence[scope_line], _ = self._evidence(scope_line, scope_row)
                memory = scope_evidence[scope_line]
                if memory['integrity'] in {'verified', 'ledger-match'}:
                    sample.update(peak_memory_bytes=scope_row['peak_memory_bytes'], memory_source=memory)
                else:
                    issues[scope_line] = memory
                break
            samples.append(sample)
        return sanitize(dict(samples=samples, summaries=summaries, issues=list(issues.values())))

    def evidence(self, line, kind: Literal['ledger', 'result']):
        rows = self._rows()
        row = rows.get(line)
        if row is None:
            raise HTTPException(404, 'Measurement ledger row not found')
        scope_lines = {number for number, _ in self._scopes(rows).values()}
        if not _benchmark_row(row) and line not in scope_lines:
            raise HTTPException(404, 'Measurement ledger row not found')
        source, result = self._evidence(line, row)
        if kind == 'result' and result is None:
            if source['integrity'] == 'mismatch':
                raise HTTPException(422, 'Measurement result is not valid JSON')
            raise HTTPException(404, 'Measurement result unavailable')
        return sanitize(dict(source=source, kind=kind, evidence=row if kind == 'ledger' else result))
