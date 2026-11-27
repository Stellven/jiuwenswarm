"""Render source-linked Run 4 measurements from the lab report's sealed files."""
from html import escape
from math import isfinite
from statistics import median

from scripts.spark.build_muse_lab_reports import a, comparison, comparison_lines, metric_chart, p, table
from scripts.spark.muse_report_memory import memory_section

ARMS = {'AQBC': 'control', 'AQBCE': 'seeded'}
CELLS = {
    'first_after_start': 'First request after ready · 512 tokens',
    'p512': 'Warm · 512 tokens',
    'p2048': 'Warm · 2048 tokens',
    'p512_followup': 'Warm follow-up · 512-token document',
    'p2048_followup': 'Warm follow-up · 2048-token document',
}
SPEED_METRICS = {
    'client_ttft_ms': ('First token', 's', 1000),
    'decode_tokens_per_second': ('Decode', 'tok/s', 1),
    'request_total_ms': ('Total request', 's', 1000),
    'cache_hit_rate': ('Expert cache hits', '%', 1),
}
CHARTS = (
    ('first-token-512', 'p512', 'client_ttft_ms'),
    ('first-token-2048', 'p2048', 'client_ttft_ms'),
    ('decode', 'p2048', 'decode_tokens_per_second'),
    ('total-2048', 'p2048', 'request_total_ms'),
    ('follow-up-2048', 'p2048_followup', 'client_ttft_ms'),
)
STARTUP_METRICS = {
    'ready_seconds': ('Process start to ready', 's'),
    'seed_fill_seconds': ('Startup seed duration', 's'),
    'seed_fill_slots': ('Populated startup slots', 'slots'),
    'seed_fill_bytes': ('Startup seed bytes', 'bytes'),
}
MATCHED_CONTEXT = 'Same delivered image. AQBC is seeding off and AQBCE is seeding on.'


def measured(value):
    return type(value) in (int, float) and isfinite(value) and value >= 0


def format_value(value, unit):
    return f'{value:.1%}' if unit == '%' else f'{value:,.2f} {unit}'


def linked_value(measurement, unit, reference=None):
    if measurement is None:
        return 'not recorded'
    value, href = measurement
    result = a(href, format_value(value, unit))
    if reference is not None:
        # Cache hit rate is a proportion, so report rate changes in points.
        result += comparison_lines([comparison('AQBC', value, reference[0], unit)])
    return result


def render_lab(values, json_files, *, historical_load=None):
    """json_files maps verified mailbox file names to (decoded data, report URL)."""
    loads = {'A': historical_load} if historical_load else {}
    for arm, label in ARMS.items():
        source = json_files.get(f'{label}-load.json')
        if source is not None:
            loads[arm] = source
    # A missing receipt is shown explicitly and never substituted with another run.
    for arm in ('A', *ARMS):
        loads.setdefault(arm, ({}, ''))
    loads = {arm: loads[arm] for arm in ('A', *ARMS)}

    metrics = {}
    for arm, label in ARMS.items():
        speed = json_files.get(f'{label}-speed.json')
        if speed is None:
            continue
        data, href = speed
        rows = data['rows']
        for cell in CELLS:
            for key, (_, _, divisor) in SPEED_METRICS.items():
                samples = [row[key] for row in rows if row.get('cell') == cell and measured(row.get(key))]
                if samples:
                    metrics[cell, key, arm] = median(samples) / divisor, href

    charts = []
    for metric, cell, key in CHARTS:
        _, unit, _ = SPEED_METRICS[key]
        base = metrics.get((cell, key, 'AQBC'))
        entries = []
        for arm in ARMS:
            observed = metrics.get((cell, key, arm))
            if observed:
                value, _ = observed
                notes = [comparison('AQBC', value, base[0], unit)] if arm == 'AQBCE' and base else []
                entries.append((arm, value, notes))
        if entries and any(value > 0 for _, value, _ in entries):
            charts.append(metric_chart(metric, f'{SPEED_METRICS[key][0]} · {CELLS[cell]}',
                                       MATCHED_CONTEXT, unit, entries, 'AQBCE'))

    rows = []
    for cell, label in CELLS.items():
        for key, (title, unit, _) in SPEED_METRICS.items():
            base = metrics.get((cell, key, 'AQBC'))
            candidate = metrics.get((cell, key, 'AQBCE'))
            if base is not None or candidate is not None:
                rows.append((escape(label), escape(title), linked_value(base, unit),
                             linked_value(candidate, unit, base)))
    body = ('<h2>Target lab verdict</h2>' + p(values['summary']) + p(MATCHED_CONTEXT)
            + p('A was not measured under the Run 4 workload. The original A load is included for memory context when available.'))
    if charts:
        body += '<h2>Performance</h2><div class="metric-charts">' + ''.join(charts) + '</div>'
    if rows:
        body += table(['Request', 'Metric', 'AQBC', 'AQBCE'], rows,
                      'Per-arm medians from the sealed request rows.')

    startup = {}
    for arm, label in ARMS.items():
        load, href = loads[arm]
        if measured(load.get('load_seconds')):
            startup['ready_seconds', arm] = load['load_seconds'], href
        fill = json_files.get(f'{label}-startup-fill.json')
        if fill is None:
            continue
        data, href = fill
        for key in STARTUP_METRICS.keys() - {'ready_seconds'}:
            value = data.get(key)
            if measured(value):
                startup[key, arm] = value, href
    startup_rows = []
    for key, (label, unit) in STARTUP_METRICS.items():
        control = startup.get((key, 'AQBC'))
        seeded = startup.get((key, 'AQBCE'))
        startup_rows.append((label, linked_value(control, unit), linked_value(seeded, unit, control)))
    body += '<h2>Ready time and startup fill</h2>' + table(
        ['Measurement', 'AQBC', 'AQBCE'], startup_rows, 'Recorded launch and startup-fill receipts.')
    body += memory_section(loads)

    checks = [(escape(check['check']), escape(check.get('arm', 'Both')),
               escape(check['verdict']), escape(check.get('detail', ''))) for check in values.get('checks', [])]
    checks.extend((escape(check['test_id']), '', 'not run', escape(check['reason'])) for check in values.get('not_run', []))
    if checks:
        body += '<h2>Lab checks</h2>' + table(['Check', 'Arm', 'Verdict', 'Detail'], checks,
                                           'Independent native lab findings.')
    return body
