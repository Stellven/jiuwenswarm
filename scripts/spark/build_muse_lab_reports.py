#!/usr/bin/env python3
"""Render the recorded Muse lab results as HTML attachments for Factory replay bundles."""
from __future__ import annotations

import argparse
from functools import cached_property
import hashlib
from html import escape
import json
from pathlib import Path
import re
from statistics import median

REPORT_PATH = 'reports/lab-report.html'
ARM_NAMES = {'A': 'A · NVFP4 baseline', 'AQB': 'AQB · mixed 2-bit + batch tuning',
             'AQBC': 'AQBC · + prefix reuse'}
TIMING_KEYS = ('ttft_ms', 'decode_tps', 'total_ms')
TIMING_UNITS = ('s', 'tok/s', 's')
START = 'warming up the model with an empty run'
SLOT = 'load_model: initializing, n_slots ='
STYLE = """
:root { color-scheme: light; font: 16px/1.55 system-ui, sans-serif; color: #18243a; background: #fff }
body { max-width: 72rem; margin: auto; padding: 1.5rem clamp(1rem, 3vw, 2rem) 3rem }
h1 { margin: 0 0 .25rem; font-size: clamp(1.65rem, 3vw, 2.3rem) }
h2 { margin: 2rem 0 .5rem; font-size: 1.35rem }
p { margin: .55rem 0 1rem }
a { color: #235aaa; text-underline-offset: .18em }
a:focus-visible { outline: 2px solid currentColor; outline-offset: .2rem }
code { overflow-wrap: anywhere; font-size: .84em }
.verdict { border-inline-start: 4px solid #2463af; padding: .65rem 1rem; background: #edf4ff }
.table { overflow-x: auto }
table { border-collapse: collapse; width: 100% }
caption { text-align: left; padding-bottom: .5rem }
th, td { text-align: left; padding: .48rem .65rem; border-bottom: 1px solid #c9d3df }
th { white-space: nowrap; background: #f0f4f9 }
td a { white-space: nowrap }
details { margin: .5rem 0 }
summary { cursor: pointer }
"""


def file_sha(raw):
    return hashlib.sha256(raw).hexdigest()


def a(href, label):
    return f'<a href="{escape(href, quote=True)}">{escape(label)}</a>'


def p(text):
    return f'<p>{escape(text)}</p>'


def table(columns, rows, caption):
    head = ''.join(f'<th scope="col">{escape(column)}</th>' for column in columns)
    body = ''.join(
        '<tr>' + ''.join(f'<td>{value}</td>' for value in row) + '</tr>' for row in rows
    )
    return (f'<div class="table"><table><caption>{escape(caption)}</caption>'
            f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def req_label(row):
    state = row['request']['state']
    if state != 'cold':
        return {'warm': 'Warm server', 'follow-up': 'Follow-up'}[state]
    if row['source']['record'] == '/rows/0':
        return 'First request after server start'
    return 'After page drop'


def clock(line):
    stamp = re.match(r'^(\d+)\.(\d{2})\.(\d{3})\.(\d{3})\b', line)
    if not stamp:
        raise ValueError(f'Unparseable elapsed timestamp: {line}')
    minute, second, millis, micros = (int(piece) for piece in stamp.groups())
    return ((60 * minute + second) * 1_000_000 + 1_000 * millis + micros) / 1_000_000


class Report:
    def __init__(self, stage, root, run):
        self.output = stage / 'reports'
        self.output.mkdir()
        (self.output / 'evidence').mkdir()
        self.root = root.resolve()
        self.run = run
        self.records = {}

    def payload(self, source):
        path = self.root / source
        if not path.resolve().is_relative_to(self.root):
            raise ValueError('Report source is outside the Muse evidence root')
        if path not in self.records:
            raw = path.read_bytes()
            self.records[path] = (raw, json.loads(raw))
        return self.records[path]

    @cached_property
    def rows(self):
        raw = (self.root / 'r9/publication/engine-bench.jsonl').read_bytes()
        return [json.loads(line) for line in raw.splitlines() if line.strip()]

    def write_json(self, relative, payload):
        (self.output / relative).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return relative

    def source(self, source, pointer, name, *, whole_file=False):
        raw, data = self.payload(source)
        if whole_file:
            relative = f'evidence/{name}.json'
            (self.output / relative).write_bytes(raw)
            return relative
        record = data
        for key in pointer.strip('/').split('/') if pointer else ():
            record = record[int(key)] if isinstance(record, list) else record[key]
        return self.write_json(f'evidence/{name}.json', {
            'source': {'file': source, 'json_pointer': pointer, 'sha256': file_sha(raw)},
            'record': record,
        })

    def linked_row(self, row):
        pointer = row['source']['record']
        absolute = Path(row['source']['path'])
        source = absolute.relative_to(self.root).as_posix()
        if row['kind'] == 'load':
            name = row['arm'].lower()
            return a(self.source(source, pointer, f'{name}-load', whole_file=True),
                     f'{name.upper()} load record · {pointer}')
        key = '-'.join((row['run'], row['arm'].lower(), row['request']['name'], pointer.rsplit('/', 1)[-1]))
        return a(self.source(source, pointer, key), pointer)

    def original_r8(self):
        report = 'r8-final/report.json'
        _, summary = self.payload(report)
        cells = []
        for row in summary['cells']:
            curated_rows = []
            for item in row['sources']:
                hit, = (r for r in self.rows if r.get('source') == item)
                curated_rows.append(hit)
            cells.append((
                row['arm'], row['request'][1:], req_label(curated_rows[0]),
                *(f'{row[key] / (1 if key == "decode_tps" else 1000):.2f}' for key in TIMING_KEYS),
                ' · '.join(self.linked_row(r) for r in curated_rows),
            ))
        return cells

    def run2_results(self):
        groups = {}
        for row in self.rows:
            if row['run'] == 'r9-aqbc' and row['kind'] == 'performance':
                req = row['request']
                groups.setdefault((req['name'][1:], req_label(row), row['arm']), []).append(row)
        return [
            (arm + (' control' if arm == 'AQB' else ''), tokens, state,
             *(f'{median(r["metrics"][key] for r in rows) / (1 if key == "decode_tps" else 1000):.2f}'
               for key in TIMING_KEYS),
             ' · '.join(self.linked_row(r) for r in rows))
            for (tokens, state, arm), rows in groups.items()
        ]

    def warmup(self):
        loads = [row for row in self.rows if row['kind'] == 'load'
                 and (self.run == 2 or row['arm'] != 'AQBC')]
        log_paths = {'A': 'lab/r8-final-bench/5.server.log', 'AQB': 'lab/r8-final-bench/3.server.log',
                     'AQBC': 'lab/r9-aqbc/measure-engine/server.log'}
        rows = []
        for row in loads:
            arm = row['arm']
            source = log_paths[arm]
            raw = (self.root / source).read_bytes()
            lines = raw.decode().splitlines()
            start = next(i for i, line in enumerate(lines) if START in line)
            end = next(i for i, line in enumerate(lines) if i > start and SLOT in line)
            excerpt = f'Source: {source}\nSHA-256: {file_sha(raw)}\n\n' + '\n'.join(
                f'{i + 1}: {lines[i]}' for i in (start, end))
            link = f'evidence/{arm.lower()}-startup-markers.log'
            (self.output / link).write_text(excerpt + '\n', encoding='utf-8')
            rows.append((arm, f'{row["metrics"]["load_s"]:.2f}', f'{clock(lines[end]) - clock(lines[start]):.2f}',
                         a(link, 'Server log markers') + ' · ' + self.linked_row(row)))
        return ('<h2>Load and warm-up record</h2>' + table(
            ['Engine', 'Launch to ready (s)', 'Empty-run marker to slot init (s)', 'Source'], rows,
            'Server startup on the target. The marker interval includes intervening setup and bounds the empty run.')
            + p('These deliveries have no dedicated record of an untimed, post-ready document warm-up phase. The first measured request is distinct from the server’s built-in empty-run warm-up.'))

    def method(self):
        w1 = 'lab/warmup-w1/run/report.json'
        raw, w1_data = self.payload(w1)
        w1_fields = ('index', 'document', 'condition', 'prompt_tokens', 'generated_tokens',
                     'derived_ttft_ms', 'decode_tokens_per_second', 'request_total_ms',
                     'page_cache_before', 'prompt_sha256')
        w1_requests = self.write_json('evidence/w1-requests.json', {
            'source': {'file': w1, 'json_pointer': '/rows', 'sha256': file_sha(raw)},
            'projection': 'Timing and residency fields from each W1 request',
            'rows': [{key: row[key] for key in w1_fields} for row in w1_data['rows']],
        })
        notes = ('<h2>Method</h2>'
                 + p('Warm-server numbers. The first request after a server start is slower (W1: +36 s first token at 512 tokens); dropping file pages adds about 5%.')
                 + p('W1 was a separate AQB experiment. Its first completion took 124.16 s to first token; the next five distinct documents had a median of 87.86 s. One advisory eviction increased the adjacent repeated-document result by 4.9%.')
                 + '<p>' + a(self.source(w1, '/startup_warmup', 'w1-startup'), 'W1 startup evidence')
                 + ' · ' + a(w1_requests, 'W1 request and residency summary')
                 + '</p>')
        if w1_data['startup_warmup']['status'] != 'bounded':
            raise ValueError('W1 missing expected timing evidence')
        if self.run == 1:
            notes += p('The original factory closure recorded report_inconclusive. Its quiet-machine rule excluded four of eight timing cells, leaving one eligible B/P pair. The follow-up campaign shown above records its own timing evidence.')
        else:
            notes += p("Run 2's 2048-token warm decode varied between repeats in both arms (AQBC 2.2 and 4.4 tok/s, AQB control 2.1 and 4.3), so the table's 3.28 median isn't quoted as an absolute speed; the same-server comparison holds.")
        return notes

    def original_baseline(self):
        source = 'lab/report-abcde.json'
        _, data = self.payload(source)
        picks = []
        for i, row in enumerate(data['rows']):
            if row['arm'] == 'A':
                picks.append(a(self.source(source, f'/rows/{i}', f'original-a-{i}'), f'/rows/{i}'))
        historic_load = self.source(source, '/arms/A', 'original-a-load')
        return ('<details><summary>Original Nov 25 A record (128 generated tokens)</summary>'
                + p(f'The original baseline reported {data["arms"]["A"]["load_seconds"]:.1f} s to load. '
                    'A separate empty-run timing is unavailable for this older baseline.')
                + '<p>' + a(historic_load, 'A load record · /arms/A') + '</p>'
                + '<p>Raw request rows: ' + ' · '.join(picks) + '</p></details>')

    def html(self):
        title = f'Run {self.run} lab report'
        timing = ('Engine', 'Prompt target', 'Request state', 'First token (s)', 'Decode (tok/s)', 'Total (s)', 'Raw rows')
        previous = table(timing, self.original_r8(),
                         'A baseline and the delivered AQB engine on Spark. These capped comparison cells generated 32 tokens.')
        _, r8 = self.payload('r8-final/report.json')
        acc = r8['accuracy']
        r8_accuracy = (p(f'MMLU matched set: A scored {acc["acc_ref"]:.1%} (235/250) and AQB scored '
                         f'{acc["acc_cand"]:.1%} (229/250). The paired comparison was inconclusive at the 5-point margin.')
                       + '<p>' + a(self.source('r8-final/report.json', '/accuracy', 'r8-accuracy'), 'Paired accuracy evidence') + '</p>')
        if self.run == 1:
            load, = (row for row in self.rows if row['arm'] == 'AQB' and row['kind'] == 'load')
            image = load['engine']['image']
            subtitle = 'AQB delivered · Original lab report partial'
            body = (p('The factory delivered the mixed 2-bit image and its test requirements. The corrected original lab report was accepted as a partial result. The target follow-up campaign measured capped, single-slot completions against A, the NVFP4 baseline.')
                    + '<p>' + a('../projections/lab-request-and-gate.json', 'Original lab handoff')
                    + ' · ' + a('../records/decisions.json', 'Factory closure decision 39') + '</p>'
                    + '<h2>Measurements against A</h2>' + previous + self.original_baseline() + r8_accuracy)
        else:
            name = 'lab/r9-aqbc/rejudge-owner-006.json'
            _, verdict = self.payload(name)
            _, manifest = self.payload('lab/r9-aqbc/measure-engine/measurements.json')
            if verdict['source']['sha256'] != file_sha(self.payload('lab/r9-aqbc/measure-engine/measurements.json')[0]):
                raise ValueError('Lab verdict does not bind its recorded measurement manifest')
            for file in ('load.json', 'speed.json'):
                if manifest['files'][file] != file_sha(self.payload(f'lab/r9-aqbc/measure-engine/{file}')[0]):
                    raise ValueError(f'Measurement source changed: {file}')
            image = manifest['identity']['image_id']
            subtitle = 'AQBC released · Lab acceptance passed' if verdict['done'] else 'Lab acceptance refused'
            summary = verdict['summary']
            warm_ratios = [ratio for row in summary['standard'] if row['judged']
                           for ratio in row['median_candidate_to_control'].values()]
            reuse = [(row['request'][1:], f'{row["candidate_cached_tokens"]:,} / {row["document_tokens"]:,}',
                      f'{row["control_cached_tokens"]:,}', f'{row["candidate"]["derived_ttft_ms"] / 1000:.2f}',
                      f'{row["control"]["derived_ttft_ms"] / 1000:.2f}') for row in summary['followup']]
            identity = summary['accuracy']
            body = (p('The factory handed off the configured image and test requirements. The lab agent ran the configured image on Spark with an unchanged pack and a capped, single-slot server. AQB control used the same server with prompt reuse disabled.')
                    + '<p>' + a('../projections/release.json', 'Native release decision')
                    + ' · ' + a(self.source(name, '', 'r9-acceptance'), 'Recorded lab acceptance checks and summary') + '</p>'
                    + '<h2>Lab acceptance</h2>'
                    + p(f'Same as AQB within the lab acceptance checker’s {summary["standard_regression_tolerance"]:.0%} tolerance '
                        f'on the same server (measured warm ratios {min(warm_ratios):.2f} to {max(warm_ratios):.2f}).')
                    + p('Measured on a shared machine; background activity recorded, not filtered. The checker judged the warm pairs and the document follow-ups. Startup and page-drop measurements are shown for context.')
                    + table(['Document target', 'AQBC cached / document tokens', 'AQB cached', 'AQBC first token (s)', 'AQB first token (s)'],
                            reuse, 'Document follow-up reuse on the same server.')
                    + p(f'{identity["matched_letters"]}/{identity["question_count"]} answer letters matched AQB; '
                        f'{identity["zero_external_reuse"]}/{identity["question_count"]} started with zero cached tokens. '
                        + (f'AQBC inherits AQB’s {identity["inherited_accuracy"]:.1%} ({identity["inherited_correct"]}/'
                           f'{identity["source_question_count"]}) MMLU score.' if identity['status'] == 'passed'
                           else 'AQBC did not inherit the AQB MMLU score.'))
                    + '<p>' + a(self.source('lab/r9-aqbc/measure-engine/mmlu.json', '/comparison', 'r9-identity'),
                                  '25-question identity result') + '</p>'
                    + '<h2>Same-server measurements</h2>'
                    + table(timing, self.run2_results(), 'Per-cell medians; individual repeats and follow-ups are linked.')
                    + '<h2>A baseline and previous AQB engine</h2>'
                    + p('These are earlier target measurements from Run 1. Compare the same-load AQBC and AQB arms above for the acceptance decision.')
                    + previous + self.original_baseline() + r8_accuracy)
        return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>'
                f'<style>{STYLE}</style></head><body><main><h1>{title}</h1>'
                f'<p class="verdict"><strong>{escape(subtitle)}</strong><br>Engine image <code>{escape(image)}</code></p>'
                + body + self.warmup() + self.method() + '</main></body></html>\n')


def write_lab_report(stage, muse_root, run):
    if run not in (1, 2):
        raise ValueError('Select a recorded run: 1 or 2')
    report = Report(stage, muse_root, run)
    target = stage / REPORT_PATH
    target.write_text(report.html(), encoding='utf-8')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--muse-root', default=Path.home() / 'muse-demo', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--run', choices=(1, 2), required=True, type=int)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    print(write_lab_report(args.output, args.muse_root, args.run))


if __name__ == '__main__':
    main()
