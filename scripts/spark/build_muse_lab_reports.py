#!/usr/bin/env python3
"""Render the recorded Muse lab results as HTML attachments for Factory replay bundles."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import cached_property
import hashlib
from html import escape
import json
from pathlib import Path
import re
from statistics import median

REPORT_PATH = 'reports/lab-report.html'
ARM_LETTERS = (
    ('A', 'Baseline: stock llama.cpp settings with the official NVFP4 weights (529 GB) on the Spark'),
    ('Q', 'Quantization CC: routed experts requantized to a mixed 2-bit pack (IQ2_XXS gate/up, Q2_K down), 267 GB'),
    ('B', "Prefill plan CC: prefill batch sizes fitted to the target's device budget"),
    ('C', "Prefix reuse CC: the engine's built-in prompt cache turned on, so a follow-up on the same document reuses it"),
    ('D', 'Batched routed-expert launches CC: stopped before build, because the engine already batches these launches'),
)
ARM_COMPOSITION = ("An engine's name lists the CCs applied on top of A, in order: AQB = A + Q + B (Run 1), "
                   "AQBC = AQB + C (Run 2), AQBCD = AQBC + D (Run 3, not built).")
TIMING_KEYS = ('ttft_ms', 'decode_tps', 'total_ms')
CHECKER_METRICS = {
    'ttft_ms': 'derived_ttft_ms',
    'decode_tps': 'decode_tokens_per_second',
    'total_ms': 'request_total_ms',
}
WARM_SERVER = 'Warm server'
FOLLOW_UP = 'Follow-up'
FIRST_AFTER_START = 'First request after server start'
AFTER_PAGE_DROP = 'After page drop'
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
.arm-names { margin: 1rem 0; padding: .75rem 1rem; border: 1px solid #c9d3df; border-radius: .45rem }
.arm-names h2 { margin: 0 0 .4rem; font-size: 1.1rem }
.arm-names td, .arm-names th { padding: .28rem .5rem; vertical-align: top }
.arm-names p { margin: .55rem 0 0 }
"""
LAB_STYLE = """
.metric-charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 23rem), 1fr)); gap: .8rem }
.metric-chart { margin: 0; border: 1px solid #c9d3df; border-radius: .45rem; padding: .7rem .85rem }
.metric-chart figcaption { display: grid; gap: .2rem }
.chart-context, .comparison, .chart-axis { font-size: .8rem; color: #40516a }
.metric-chart dl { margin: .5rem 0 0 }
.chart-row { display: grid; grid-template-columns: 3.55rem minmax(0, 1fr); gap: .4rem; margin: .3rem 0 }
.chart-row dt { font-weight: 650; padding-block-start: .1rem }
.chart-row dd { margin: 0; min-width: 0 }
.chart-track { position: relative; isolation: isolate; background: #f0f4f9; border-radius: .2rem; overflow: hidden }
.chart-bar { position: absolute; z-index: -1; inset: 0 auto 0 0; background: #ced9e8 }
.chart-row[data-current='true'] .chart-bar { background: #91bcf7 }
.chart-row[data-current='true'] dt { color: #235aaa }
.chart-value { display: block; padding: .08rem .35rem; font-size: .88rem; font-weight: 650 }
.chart-axis { margin: 0 0 0 3.95rem; display: flex; justify-content: space-between }
.comparison { display: block; margin-top: .15rem }
.metric-value { white-space: nowrap; font-weight: 650; font-variant-numeric: tabular-nums }
.timing-table .comparison { min-width: 8.5rem }
"""


@dataclass(frozen=True)
class TimingRow:
    arm: str
    tokens: str
    state: str
    values: dict[str, float]
    sources: list[dict]

    @property
    def key(self):
        return self.tokens, self.state, self.arm


def signed(value, places, unit):
    magnitude = f'{abs(value):.{places}f}'
    sign = ('+' if value > 0 else '−') if float(magnitude) else ''
    return f'{sign}{magnitude}{unit}'


def gain(value, reference, unit):
    if unit == '%':
        difference = (value - reference) * 100
        return signed(difference, 1, ' point' if abs(round(difference, 1)) == 1 else ' points')
    if reference <= 0 or (unit == 's' and value <= 0):
        return 'relative change unavailable'
    ratio = value / reference
    change = signed((ratio - 1) * 100, 0, '%')
    if ratio == 1:
        return '1× (0%)'
    factor = max(ratio, 1 / ratio) if unit == 's' else ratio
    multiple = f'{factor:.2f}' if abs(factor - 1) < .1 else f'{factor:.1f}'
    direction = (' faster' if ratio < 1 else ' slower') if unit == 's' else ''
    return f'{multiple.rstrip("0").rstrip(".")}×{direction} ({change})'


def comparison(arm, value, reference, unit, *, context='', same=False):
    if same:
        return f'same as {arm}'
    label = f'vs {arm} ({context})' if context else f'vs {arm}'
    result = gain(value, reference, unit) if reference is not None else 'no matched measurement'
    return f'{label} — {result}'


def comparison_lines(lines):
    return ''.join(f'<span class="comparison">{escape(line)}</span>' for line in lines)


def value_label(value, unit):
    return f'{value:.1%}' if unit == '%' else f'{value:.2f} {unit}'


def metric_cell(value, unit, notes):
    return f'<span class="metric-value">{escape(value_label(value, unit))}</span>' + comparison_lines(notes)


def metric_chart(metric, title, context, unit, rows, current):
    ceiling = 1 if unit == '%' else max(value for _, value, _ in rows)
    if ceiling <= 0:
        raise ValueError(f'Chart {metric} has no positive scale')
    entries = []
    for arm, value, notes in rows:
        width = 100 * value / ceiling
        entries.append(
            f'<div class="chart-row" data-arm="{escape(arm)}" data-value="{value}"'
            f' data-current="{str(arm == current).lower()}"><dt>{escape(arm)}</dt><dd>'
            f'<div class="chart-track"><span class="chart-bar" aria-hidden="true" style="width:{width:.8f}%"></span>'
            f'<span class="chart-value">{escape(value_label(value, unit))}</span></div>'
            f'{comparison_lines(notes)}</dd></div>'
        )
    return (f'<figure class="metric-chart" data-metric="{escape(metric)}" data-axis-max="{ceiling}">'
            f'<figcaption><strong>{escape(title)}</strong><span class="chart-context">{escape(context)}</span></figcaption>'
            f'<dl>{"".join(entries)}</dl><p class="chart-axis" aria-hidden="true"><span>0</span>'
            f'<span>{escape(value_label(ceiling, unit))}</span></p></figure>')


def file_sha(raw):
    return hashlib.sha256(raw).hexdigest()


def a(href, label):
    return f'<a href="{escape(href, quote=True)}">{escape(label)}</a>'


def p(text):
    return f'<p>{escape(text)}</p>'


def table(columns, rows, caption, *, css_class=''):
    head = ''.join(f'<th scope="col">{escape(column)}</th>' for column in columns)
    body = ''.join(
        '<tr>' + ''.join(f'<td>{value}</td>' for value in row) + '</tr>' for row in rows
    )
    classes = f'table {css_class}' if css_class else 'table'
    return (f'<div class="{classes}"><table><caption>{escape(caption)}</caption>'
            f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def arm_names_box():
    rows = ''.join(f'<tr><th scope="row">{letter}</th><td>{escape(meaning)}</td></tr>'
                   for letter, meaning in ARM_LETTERS)
    return ('<section class="arm-names" aria-labelledby="arm-names-title">'
            '<h2 id="arm-names-title">What the names mean</h2>'
            '<table><thead><tr><th scope="col">Letter</th><th scope="col">Meaning</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>' + p(ARM_COMPOSITION) + '</section>')


def req_label(row):
    state = row['request']['state']
    if state != 'cold':
        return {'warm': WARM_SERVER, 'follow-up': FOLLOW_UP}[state]
    if row['source']['record'] == '/rows/0':
        return FIRST_AFTER_START
    return AFTER_PAGE_DROP


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

    @cached_property
    def original_r8(self):
        report = 'r8-final/report.json'
        _, summary = self.payload(report)
        cells = {}
        for row in summary['cells']:
            curated_rows = []
            for item in row['sources']:
                hit, = (r for r in self.rows if r.get('source') == item)
                curated_rows.append(hit)
            cell = TimingRow(row['arm'], row['request'][1:], req_label(curated_rows[0]),
                             {key: row[key] for key in TIMING_KEYS}, curated_rows)
            cells[cell.key] = cell
        return cells

    @cached_property
    def run2_results(self):
        groups = {}
        for row in self.rows:
            if row['run'] == 'r9-aqbc' and row['kind'] == 'performance':
                req = row['request']
                groups.setdefault((req['name'][1:], req_label(row), row['arm']), []).append(row)
        return {
            (tokens, state, arm): TimingRow(arm, tokens, state, {
                key: median(row['metrics'][key] for row in rows) for key in TIMING_KEYS
            }, rows)
            for (tokens, state, arm), rows in groups.items()
        }

    def timing_comparisons(self, row, key, *, acceptance=None):
        if row.arm == 'A':
            return []
        time_or_rate = 'tok/s' if key == 'decode_tps' else 's'
        base = self.original_r8.get((row.tokens, row.state, 'A'))
        notes = [comparison('A', row.values[key], base.values[key] if base else None, time_or_rate,
                            context='Run 1 reference' if base and acceptance is not None else '')]
        if row.arm == 'AQBC' and acceptance is not None:
            prior = self.run2_results.get((row.tokens, row.state, 'AQB'))
            context = ''
            if prior is None and row.state == FIRST_AFTER_START:
                # Both cold requests used page eviction. Only the candidate went first.
                prior = self.run2_results.get((row.tokens, AFTER_PAGE_DROP, 'AQB'))
                context = 'same server, later cold request'
            judgement = next((group for group in acceptance['standard']
                              if group['judged'] and row.state == WARM_SERVER
                              and group['request'] == f'p{row.tokens}'), None)
            matched_ratio = judgement['median_candidate_to_control'][CHECKER_METRICS[key]] if judgement else None
            same = (prior is not None and matched_ratio is not None
                    and abs(matched_ratio - 1) <= acceptance['standard_regression_tolerance'])
            notes.append(comparison('AQB', row.values[key], prior.values[key] if prior else None,
                                    time_or_rate, context=context if prior else '', same=same))
        return notes

    def timing_cell(self, row, key, *, acceptance=None):
        unit = 'tok/s' if key == 'decode_tps' else 's'
        value = row.values[key] / (1000 if unit == 's' else 1)
        notes = self.timing_comparisons(row, key, acceptance=acceptance)
        return f'<span class="metric-value">{value:.2f}</span>' + comparison_lines(notes)

    def timing_table(self, columns, cells, caption, *, acceptance=None):
        rows = [
            (row.arm + (' control' if row.arm == 'AQB' and acceptance is not None else ''),
             row.tokens, row.state, *(self.timing_cell(row, key, acceptance=acceptance) for key in TIMING_KEYS),
             ' · '.join(self.linked_row(source) for source in row.sources))
            for row in cells.values()
        ]
        return table(columns, rows, caption, css_class='timing-table')

    def timing_charts(self, *, acceptance=None):
        current = 'AQBC' if acceptance is not None else 'AQB'
        context = ('Warm server. A is the Run 1 reference; AQB and AQBC ran on the same server in Run 2.'
                   if acceptance is not None else 'Warm server on Spark, with 32 generated tokens.')
        metrics = [
            ('first-token-512', 'First token · 512-token prompt', '512', WARM_SERVER, 'ttft_ms'),
            ('first-token-2048', 'First token · 2048-token prompt', '2048', WARM_SERVER, 'ttft_ms'),
            ('decode', 'Decode · 512-token prompt', '512', WARM_SERVER, 'decode_tps'),
            ('total-2048', 'Total request · 2048-token prompt', '2048', WARM_SERVER, 'total_ms'),
        ]
        if acceptance is not None:
            metrics.append(('follow-up-2048', 'Follow-up first token · 2048-token document',
                            '2048', FOLLOW_UP, 'ttft_ms'))
        rows = self.original_r8
        if acceptance is not None:
            rows = {**rows, **self.run2_results}
        for name, label, target, state, key in metrics:
            followup = state == FOLLOW_UP
            arms = ('AQB', 'AQBC') if followup else ('A', 'AQB', 'AQBC') if acceptance is not None else ('A', 'AQB')
            unit = 'tok/s' if key == 'decode_tps' else 's'
            entries = []
            for arm in arms:
                row = rows[target, state, arm]
                value = row.values[key] / (1000 if unit == 's' else 1)
                entries.append((arm, value, self.timing_comparisons(row, key, acceptance=acceptance)))
            chart_context = ('Same-document, same-server pair. No matched A follow-up was recorded.'
                             if followup else context)
            yield metric_chart(name, label, chart_context, unit, entries, current)

    def accuracy_chart(self, acc, *, identity=None):
        a_score, aqb_score = acc['acc_ref'], acc['acc_cand']
        rows = [('A', a_score, []),
                ('AQB', aqb_score, [comparison('A', aqb_score, a_score, '%')])]
        context = f'Paired Run 1 MMLU set, {acc["n"]} questions.'
        current = 'AQB' if identity is None else 'AQBC'
        if identity is not None and identity['status'] == 'passed':
            inherited = identity['inherited_accuracy']
            notes = [comparison('A', inherited, a_score, '%')]
            notes.append(comparison('AQB', inherited, aqb_score, '%', same=inherited == aqb_score))
            rows.append(('AQBC', inherited, notes))
            context += ' AQBC inherits AQB’s score through the identity check.'
        return metric_chart('mmlu', 'MMLU accuracy', context, '%', rows, current)

    def charts(self, acc, *, acceptance=None):
        identity = acceptance['accuracy'] if acceptance is not None else None
        return ('<h2>Performance and accuracy</h2><div class="metric-charts">'
                + ''.join(self.timing_charts(acceptance=acceptance))
                + self.accuracy_chart(acc, identity=identity) + '</div>')

    def warmup(self):
        loads = [row for row in self.rows if row['kind'] == 'load'
                 and (self.run == 2 or row['arm'] != 'AQBC')]
        log_paths = {'A': 'lab/r8-final-bench/5.server.log', 'AQB': 'lab/r8-final-bench/3.server.log',
                     'AQBC': 'lab/r9-aqbc/measure-engine/server.log'}
        records = {}
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
            records[arm] = (row['metrics']['load_s'], clock(lines[end]) - clock(lines[start]),
                            a(link, 'Server log markers') + ' · ' + self.linked_row(row))
        rows = []
        for arm, (load, interval, source) in records.items():
            references = [] if arm == 'A' else ['A']
            if arm == 'AQBC':
                references.append('AQB')
            notes = [
                [comparison(ref, value, records[ref][index], 's',
                            context='Run 1 reference' if arm == 'AQBC' else '') for ref in references]
                for index, value in enumerate((load, interval))
            ]
            rows.append((arm, metric_cell(load, 's', notes[0]), metric_cell(interval, 's', notes[1]), source))
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
        previous = self.timing_table(timing, self.original_r8,
            'A baseline and the delivered AQB engine on Spark. These capped comparison cells generated 32 tokens.')
        _, r8 = self.payload('r8-final/report.json')
        acc = r8['accuracy']
        r8_accuracy = (p(f'MMLU matched set: A answered {acc["both_right"] + acc["ref_only"]}/{acc["n"]} correctly '
                         f'and AQB answered {acc["both_right"] + acc["cand_only"]}/{acc["n"]} correctly. '
                         f'The paired comparison was inconclusive at the {acc["margin_pts"]}-point margin.')
                       + '<p>' + a(self.source('r8-final/report.json', '/accuracy', 'r8-accuracy'), 'Paired accuracy evidence') + '</p>')
        if self.run == 1:
            load, = (row for row in self.rows if row['arm'] == 'AQB' and row['kind'] == 'load')
            image = load['engine']['image']
            subtitle = 'AQB delivered · Original lab report partial'
            body = (p('The factory delivered the mixed 2-bit image and its test requirements. The corrected original lab report was accepted as a partial result. The target follow-up campaign measured capped, single-slot completions against A, the NVFP4 baseline.')
                    + '<p>' + a('../projections/lab-request-and-gate.json', 'Original lab handoff')
                    + ' · ' + a('../records/decisions.json', 'Factory closure decision 39') + '</p>'
                    + self.charts(acc) + '<h2>Measurements against A</h2>'
                    + previous + self.original_baseline() + r8_accuracy)
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
            reuse = []
            for row in summary['followup']:
                target = row['request'][1:]
                cached = row['candidate_cached_tokens']
                control_cached = row['control_cached_tokens']
                cached_notes = (comparison('AQB', cached, control_cached, 'tokens') if control_cached else
                                f'vs AQB — {cached - control_cached:+,} cached tokens; relative gain undefined from zero')
                candidate = self.run2_results[target, FOLLOW_UP, 'AQBC']
                control = self.run2_results[target, FOLLOW_UP, 'AQB']
                reuse.append((target, f'{cached:,} / {row["document_tokens"]:,}' + comparison_lines([cached_notes]),
                              f'{control_cached:,}', self.timing_cell(candidate, 'ttft_ms', acceptance=summary),
                              self.timing_cell(control, 'ttft_ms', acceptance=summary)))
            identity = summary['accuracy']
            body = (p('The factory handed off the configured image and test requirements. The lab agent ran the configured image on Spark with an unchanged pack and a capped, single-slot server. AQB control used the same server with prompt reuse disabled.')
                    + '<p>' + a('../projections/release.json', 'Native release decision')
                    + ' · ' + a(self.source(name, '', 'r9-acceptance'), 'Recorded lab acceptance checks and summary') + '</p>'
                    + self.charts(acc, acceptance=summary)
                    + '<h2>Lab acceptance</h2>'
                    + p(f'Same as AQB within the lab acceptance checker’s {summary["standard_regression_tolerance"]:.0%} tolerance '
                        f'on the same server (measured warm ratios {min(warm_ratios):.2f} to {max(warm_ratios):.2f}).')
                    + p('Measured on a shared machine; background activity recorded, not filtered. The checker judged the warm pairs and the document follow-ups. Startup and page-drop measurements are shown for context.')
                    + table(['Document target', 'AQBC cached / document tokens', 'AQB cached', 'AQBC first token (s)', 'AQB first token (s)'],
                            reuse, 'Document follow-up reuse on the same server.')
                    + p(f'{identity["matched_letters"]}/{identity["question_count"]} answer letters matched AQB; '
                        f'{identity["zero_external_reuse"]}/{identity["question_count"]} started with zero cached tokens. '
                        + (f'AQBC inherits AQB’s MMLU score ({identity["inherited_correct"]}/'
                           f'{identity["source_question_count"]}).' if identity['status'] == 'passed'
                           else 'AQBC did not inherit the AQB MMLU score.'))
                    + '<p>' + a(self.source('lab/r9-aqbc/measure-engine/mmlu.json', '/comparison', 'r9-identity'),
                                  '25-question identity result') + '</p>'
                    + '<h2>Same-server measurements</h2>'
                    + self.timing_table(timing, self.run2_results,
                                        'Per-cell medians; individual repeats and follow-ups are linked.',
                                        acceptance=summary)
                    + '<h2>A baseline and previous AQB engine</h2>'
                    + p('These are earlier target measurements from Run 1. Compare the same-load AQBC and AQB arms above for the acceptance decision.')
                    + previous + self.original_baseline() + r8_accuracy)
        return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>'
                f'<style>{STYLE}{LAB_STYLE}</style></head><body><main><h1>{title}</h1>'
                f'<p class="verdict"><strong>{escape(subtitle)}</strong><br>Engine image <code>{escape(image)}</code></p>'
                + arm_names_box() + body + self.warmup() + self.method() + '</main></body></html>\n')


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
