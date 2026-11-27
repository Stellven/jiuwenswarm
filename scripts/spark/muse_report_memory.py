"""Memory section from capped Muse server load receipts."""
from html import escape

MIB = 1024 ** 2
METRICS = (
    ('pack', 'Weights on disk', 'GB'), ('rss', 'Peak server RSS', 'MiB'),
    ('cap', 'Host cap', 'MiB'), ('floor', 'Lowest MemAvailable', 'MiB'),
    ('configured', 'GPU expert cache setting', 'MiB'), ('model', 'Device model', 'MiB'),
    ('moe_cache', 'Allocated expert cache', 'MiB'), ('kv', 'KV cache', 'MiB'),
    ('compute', 'Compute', 'MiB'), ('host_compute', 'Host compute', 'MiB'),
    ('total', 'Total accounted', 'MiB'), ('budget', 'Device budget', 'MiB'),
    ('headroom', 'Budget headroom', 'MiB'), ('fit', 'Placement fit margin', 'MiB'),
)


def scaled(value, divisor):
    return None if value is None else value / divisor


def memory_values(load):
    pack = load.get('pack') or load.get('identity', {}).get('pack', {})
    argv = load.get('argv', [])
    configured = int(argv[argv.index('--moe-cache-mib') + 1]) if '--moe-cache-mib' in argv else None
    components = load.get('observed', {}).get('device_mib', {})
    parts = [components.get(k) for k in ('model', 'moe_cache', 'kv', 'compute', 'host_compute')]
    total = sum(parts) if all(p is not None for p in parts) else None
    budget = load.get('device_budget_mib')
    return {**components, 'pack': scaled(pack.get('bytes'), 1e9),
            'rss': scaled(load.get('peak_process_rss_bytes'), MIB),
            'floor': scaled(load.get('min_available_bytes'), MIB),
            'cap': 98304 if load.get('memory_cap') == '96G' else None,
            'configured': configured, 'budget': budget, 'total': total,
            'headroom': budget-total if budget is not None and total is not None else None,
            'fit': load.get('placement', {}).get('fit_margin_mib')}


def formatted(value, unit):
    return f'{value:,.1f}' if unit == 'GB' else f'{value:,.2f}'.removesuffix('.00')


def memory_section(records):
    """Ordered mapping from engine name to (decoded load record, evidence URL)."""
    from scripts.spark.build_muse_lab_reports import table

    values = {arm: memory_values(load) for arm, (load, _) in records.items()}
    def linked(arm, label):
        return f'<a href="{escape(records[arm][1], quote=True)}">{escape(label)}</a>'

    rows = []
    for key, label, unit in METRICS:
        cells = []
        for index, (arm, data) in enumerate(values.items()):
            value = data.get(key)
            if value is None:
                cells.append('not recorded')
                continue
            cell = linked(arm, formatted(value, unit))
            references = list(values)[:1] if index else []
            if index > 1:
                references.append(list(values)[index-1])
            for ref in references:
                base = values[ref].get(key)
                if base is None:
                    continue
                diff = value - base
                delta = ('+' if diff > 0 else '−' if diff < 0 else '') + formatted(abs(diff), unit)
                change = f' ({100*diff/base:+.2f}%)' if base else ''
                cell += '<small class="comparison">' + linked(ref, 'vs '+ref) + ' ' + linked(arm, delta+' '+unit+change) + '</small>'
            cells.append(cell)
        rows.append((escape(label+' ('+unit+')'), *cells))

    panels = []
    for key, title, unit in [('rss', 'Peak host memory', 'MiB'), ('pack', 'Weights on disk', 'GB')]:
        caps = [v['cap'] for v in values.values() if v['cap'] is not None] if key == 'rss' else []
        scale = max([v[key] for v in values.values() if v.get(key) is not None] + caps, default=1) or 1
        bars = []
        for arm, data in values.items():
            val = data.get(key)
            if val is None:
                bars.append(f'<div>{escape(arm)} · not recorded</div>')
                continue
            cap = data['cap']
            marker = (f'<i class="cap-line" style="left:calc({100*cap/scale:.6f}% - 2px)"></i>'
                      if key == 'rss' and cap is not None else '')
            bars.append(f'<div class="chart-row"><b>{escape(arm)}</b><div class="chart-track">'
                        f'<span class="chart-bar" style="width:{100*val/scale:.6f}%"></span>'
                        +marker+'<span class="chart-value">'+linked(arm, formatted(val, unit)+' '+unit)+'</span></div></div>')
        caption = ' · line = '+', '.join(formatted(c, unit)+' MiB cap' for c in sorted(set(caps))) if caps else ''
        panels.append('<div><strong>'+title+'</strong>'+escape(caption)+''.join(bars)+'</div>')
    return ('<section id="memory"><h2>Memory</h2><figure class="metric-chart memory-chart"><figcaption>'
            'Peak host memory and weights on disk</figcaption>'+''.join(panels)+'</figure>'
            + table(['Measurement', *records], rows, 'Capped server load records. Total accounted includes host compute.')
            + '</section>')
