"""Self-contained static HTML: inline SVG, CSS, JS and normalized evidence JSON."""
from __future__ import annotations

import html
import json

from ..redact import sanitize
from .activity import READINESS, SCHEMA


def _text(value):
    if value is None or value == '':
        return 'UNKNOWN'
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _h(value):
    return html.escape(_text(value), quote=True)


def _ms(value):
    if value is None:
        return 'UNKNOWN'
    if 0 < value < 1000:
        return f'{value:g} ns'
    if 1000 <= value < 1_000_000:
        return f'{value / 1000:,.3f} µs'
    return f'{value / 1_000_000:,.3f} ms'


def _bytes(value):
    if value is None:
        return 'UNKNOWN'
    for power, unit in ((30, 'GiB'), (20, 'MiB'), (10, 'KiB')):
        if value >= 2**power:
            return f'{value / 2**power:,.3f} {unit}'
    return f'{value:,} bytes'


def _metric(label, value, note=''):
    return f'<div class="metric"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong><small>{html.escape(note)}</small></div>'


def _source_refs(doc, *kinds):
    found = [f'S{i + 1}' for i, s in enumerate(doc['provenance']['source_files']) if s['kind'] in kinds]
    return ', '.join(found) or 'UNKNOWN'


def _panel_meta(source, coverage, unit):
    return f'<p class="panel-meta">Source: {_h(source)} · Coverage: {_h(coverage)} · Unit: {_h(unit)}</p>'


def _event_detail(event):
    spec = event['speculative']
    return '\n'.join([
        f"Run {event['run_id']} · {event['phase']} token {event['token_idx']} · layer {event['layer']}",
        'Selected IDs: ' + _text(event['selected_ids']), 'Predicted IDs: ' + _text(event['predicted_ids']),
        'Prediction source: ' + _text(event['prediction_source']),
        'Readiness at arrival: ' + (', '.join(f"{r['expert_id']}:{r['class'].upper()}" for r in event['readiness']) or 'UNKNOWN'),
        f"Demand read: {_text(event['demand_read_bytes'])} bytes · demand wait: {_text(event['demand_wait_ns'])} ns",
        'Speculative bytes: ' + ', '.join(f'{k}={_text(spec[k])}' for k in ('issued_bytes', 'read_bytes', 'used_bytes', 'wasted_bytes', 'timely_bytes', 'late_bytes')),
        'Unused scope: ' + _text(spec['unused_scope']),
        f"Monotonic arrival: {_text(event['arrival_ns'])} ns · fill end: {_text(event['fill_end_ns'])} ns",
        'Source: ' + event['source'],
    ])


def _initial_map(doc):
    """Initial SVG is useful even with JS disabled; JS supplies paging/details."""
    events = doc['activity']['events']
    session = doc['activity']['sessions'][0] if doc['activity']['sessions'] else None
    rows = [(i, e) for i, e in enumerate(events) if e['run_id'] == session and e['phase'] == 'decode']
    if not rows:
        return '<div class="empty">UNKNOWN<br><small>aggregate, no per-token trace</small></div>'
    tokens = sorted({r['token_idx'] for _, r in rows})[:64]
    layers = list(range(doc['model']['n_layers'])) if doc['model']['n_layers'] else sorted({r['layer'] for _, r in rows})
    width, height = max(480, len(tokens) * 12 + 44), max(80, len(layers) * 10 + 32)
    dx = (width - 44) / max(1, len(tokens))
    indexed = {(e['layer'], e['token_idx']): (i, e) for i, e in rows}
    svg = [f'<svg role="img" aria-label="Decode layer by token activity map" viewBox="0 0 {width} {height}">']
    for column, token in enumerate(tokens):
        if column % 4 == 0:
            svg.append(f'<text x="{40 + column * dx:.2f}" y="12" class="axis">{token}</text>')
    for row, layer in enumerate(layers):
        y = 22 + row * 10
        svg.append(f'<text x="2" y="{y + 7}" class="axis">L{layer}</text>')
        for column, token in enumerate(tokens):
            x = 40 + column * dx
            pair = indexed.get((layer, token))
            if pair is None:
                svg.append(f'<rect x="{x:.2f}" y="{y}" width="{dx - 1:.2f}" height="8" class="state-unknown"><title>Unobserved layer/token: UNKNOWN</title></rect>')
                continue
            index, event = pair
            states = [s['class'] for s in event['readiness']] or ['unknown']
            svg.append(f'<g tabindex="0" role="button" data-event="{index}" aria-label="Token {token}, layer {layer}; show expert details"><title>{html.escape(_event_detail(event))}</title>')
            for slot, state in enumerate(states):
                svg.append(f'<rect x="{x + slot * (dx - 1) / len(states):.2f}" y="{y}" width="{(dx - 1) / len(states):.2f}" height="8" class="state-{state}"/>')
            svg.append('</g>')
    svg.append('</svg>')
    return ''.join(svg)


def _changes(doc):
    if not doc['changes']:
        return '<div class="empty">UNKNOWN<small>No linked factory component/decision evidence in this source.</small></div>'
    rows = []
    for change in doc['changes']:
        status = 'recorded applied/kept' if change['applied'] is True else 'recorded not applied' if change['applied'] is False else 'applied status UNKNOWN'
        rows.append(f'''<li><strong>{_h(change['component'])}</strong> <span class="badge">{_h(change['action'])}</span> · {status}
<p>Commit <code>{_h(change['source_commit'])}</code> → files <code>{_h(change['files_changed'])}</code></p>
<p>Reason: {_h(change['reason'])}<br><small>Evidence IDs: {_h(change['evidence_ids'])}</small></p>
<p>Effective config: <code>{_h(change['effective_config'])}</code> → image <code>{_h(change['image_id'])}</code></p>
<p>Observation: engagement {_h(change['engagement'])}<br>A/B {_h(change['ab_result'])}</p>
<small>Source: {_h(change['source'])} · {_h(change['coverage'])}</small></li>''')
    return '<ol class="changes">' + ''.join(rows) + '</ol>'


def render_html(document):
    """Return a complete offline page. Evidence text is escaped, never executed."""
    doc = sanitize(document)
    if doc.get('schema') != SCHEMA:
        raise ValueError('Expected expert_activity/1')
    provenance = doc['provenance']
    mode = {'replay': 'REPLAY · recorded evidence', 'live': 'LIVE EVIDENCE SNAPSHOT · no polling',
            'synthetic': 'SYNTHETIC · test/example data'}.get(provenance['mode'], 'UNKNOWN provenance mode')
    phase_cards = []
    for phase in ('load', 'prompt', 'decode'):
        p = doc['phases'][phase]
        phase_cards.append(f'''<div><b>{phase.upper()}</b><strong>{_ms(p['duration_ns'])}</strong>
<small>{_h(p['tokens'])} tokens · fill pread {_bytes(p['demand_read_bytes'])} · fill wait {_ms(p['demand_wait_ns'])}<br>
{_h(p['demand_calls'])} fill calls · {_h(p['coverage'])}; {_h(p['trace_records'])} observed trace rows</small></div>''')
    totals = doc['totals']
    read_metrics = ''.join([
        _metric('Demand pread', _bytes(totals['demand_read_bytes']), 'teardown total across covered phases'),
        _metric('Speculative pread', _bytes(totals['speculative_read_bytes']), 'decode pregate actual read volume'),
        _metric('Unused at target', _bytes(totals['speculative_unused_target_bytes']), 'not lifetime nonuse'),
        _metric('Never used in run', _bytes(totals['speculative_unused_lifetime_bytes']), 'requires end-of-run use tracking'),
    ])
    pregate = doc['stats'].get('pregate') or {}
    recall = pregate.get('recall_at_k') if pregate.get('actual', 0) else None
    recall_text = 'UNKNOWN' if recall is None else f'{recall * 100:.2f}%'
    completion = ' · '.join(f'{label} {_text(pregate.get(key))}' for key, label in
        [('hit_done', 'done'), ('hit_resident', 'resident at prediction'), ('hit_inflight', 'in flight'), ('hit_queued', 'queued')])
    readiness = doc['stats'].get('readiness') or {}
    arrival = ' · '.join(f'{label} {_bytes(readiness.get(key))}' for key, label in
        [('decode_ready_bytes_predicted', 'predicted ready'), ('decode_missing_bytes_predicted', 'predicted missing'),
         ('decode_ready_bytes_unpredicted', 'unpredicted ready'), ('decode_missing_bytes_unpredicted', 'unpredicted missing')])
    placement = provenance['placement']
    legend = ''.join(f'<span><i class="state-{state}"></i>{state.upper()}</span>' for state in READINESS)
    sources = ''.join(f'''<li id="source-{i + 1}"><b>S{i + 1} · {_h(s['kind'])}</b> <code>{_h(s['path'])}</code>
<br>Coverage: {_h(s['coverage'])}<br>SHA256: <code>{_h(s['sha256'])}</code>
<br>Overhead: {_h(s['overhead']['mode'])}; measured ratio {_h(s['overhead']['measured_ratio'])}; evidence ID {_h(s['overhead']['evidence_id'])}</li>'''
        for i, s in enumerate(provenance['source_files']))
    notes = ''.join('<li>' + _h(note) + '</li>' for note in doc['notes'])
    stats_json = html.escape(json.dumps(doc['stats'], ensure_ascii=False, indent=2))
    thread_json = html.escape(json.dumps(doc['threads'], ensure_ascii=False, indent=2)) if doc['threads'] else 'UNKNOWN'
    serialized = json.dumps(doc, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    # A JSON script element is still HTML raw text: escape closing tags and JS separators.
    serialized = serialized.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    html_page = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>Expert activity · __RUN__</title><style>__CSS__</style></head><body>
<header><div><p class="eyebrow">EXPERT ACTIVITY / CHANGE OBSERVABILITY</p><h1>__RUN__</h1><p><span class="badge">__MODE__</span> · Offline view · bytes / ns normalized as expert_activity/1</p></div>
<div class="tools"><button id="theme" type="button">Light / dark</button><button id="download" type="button">Download JSON</button></div></header>
<div class="provenance"><span>Image ID <code>__IMAGE__</code> · reference <code>__IMAGE_REF__</code></span><br>
<span>Effective config <code>__CONFIG__</code></span><br><span>Compute: experts __EXPERTS__ · non-expert __NONEXPERT__</span><small>__PLACEMENT_NOTE__</small></div>
<div class="phases">__PHASES__</div>
<div class="controls"><label>Trace session <select id="session" aria-label="Trace session"></select></label><label>Phase <select id="phase"><option value="decode">decode</option><option value="prompt">prompt</option><option value="load">load</option><option value="unknown">UNKNOWN phase</option></select></label>
<button id="previous" type="button">← Tokens</button><button id="next" type="button">Tokens →</button><span id="page-note"></span></div>
<main><section id="activity-panel"><h2>A · Selected experts and readiness</h2>__ACTIVITY_META__
<div class="legend">__LEGEND__</div><div id="map" class="map">__MAP__</div>
<p class="caption">x: token index · y: layer · each cell contains the selected experts, coloured by readiness at arrival. Hover, click or focus a cell for IDs and exact bytes/ns. Missing cells are UNKNOWN.</p>
<pre id="cell-detail" class="cell-detail">Select a cell. Per-cell data UNKNOWN until an expert trace is available.</pre></section>
<section id="prediction-panel"><h2>B · Predicted versus selected</h2>__PREDICTION_META__
<div class="metrics">__READ_METRICS__</div><p>Aggregate recall <strong>__RECALL__</strong> · predicted-layer denominator __ACTUAL__ selected IDs (lookahead distances may repeat selected IDs).</p>
<p class="caption">Legacy selected-hit completion buckets: __COMPLETION__. Completion is not arrival residency. No aggregate bucket colours the map.</p>
<p class="caption">Demand-fill residency probes (patch 10): __ARRIVAL__</p>
<p id="trace-totals" class="caption">Traced-cell demand / speculative byte totals: UNKNOWN</p>
<div id="prediction-table" class="table-wrap"></div>
<p class="caption">Per-layer recall uses only traced records with observed predictions. Ready/late counts are selected predicted IDs; read/issued/used/unused values are speculative bytes for the observed target cells. UNKNOWN fields never become zero. Lifetime nonuse requires end_of_run scope.</p></section>
<section id="timeline-panel"><h2>C · Where execution waited</h2>__TIMELINE_META__
<div id="timeline" class="timeline"></div><p class="caption">Demand-fill wait includes setup, probes, pread waits and joins on the main thread. Rest-of-token is an inferred residual, with no CPU/GPU compute attribution.</p>
<p>Aggregate demand wait __WAIT__ · reported mean __WAIT_MEAN__ per filled token<br>Join subset __JOIN_WAIT__ · joins __JOIN_COUNT__ · joined __JOIN_BYTES__</p>
<details><summary>Sampled threads: coverage and collection overhead</summary><p>Thread states are sampled; they do not measure per-layer wait or GPU computation. Reconstructed phase boundaries are inferred, with the recorded error bounds. Sampler self CPU is not an engine overhead ratio.</p><pre>__THREADS__</pre></details></section>
<section id="change-panel"><h2>D · What changed and why</h2>__CHANGE_META____CHANGES__</section></main>
<footer><details open><summary>Provenance, coverage, sampling and overhead</summary><p>View generation is offline, outside inference. Stats-line emission: negligible (declared). Trace overhead: operator A/B required; UNKNOWN until measured. Ratio = instrumented / uninstrumented wall time; a sampler CPU percentage or performance speedup is not this ratio.</p>
<p>__SAMPLING__</p><ul>__NOTES__</ul><ol class="sources">__SOURCES__</ol></details>
<details><summary>Raw parsed stats with source lines</summary><pre>__STATS__</pre></details></footer>
<script id="activity-data" type="application/json">__DATA__</script><script>__JS__</script></body></html>'''
    replacements = {
        'RUN': _h(provenance['run_id']), 'MODE': _h(mode), 'IMAGE': _h(provenance['image_id']),
        'IMAGE_REF': _h(provenance['image_ref']), 'CONFIG': _h(provenance['effective_config_line']),
        'EXPERTS': _h(placement['experts']), 'NONEXPERT': _h(placement['non_expert']),
        'PLACEMENT_NOTE': _h(placement['note']) + ' Source: ' + _h(placement['source']),
        'PHASES': ''.join(phase_cards), 'LEGEND': legend, 'MAP': _initial_map(doc),
        'ACTIVITY_META': _panel_meta(_source_refs(doc, 'expert-trace', 'engine-stats'), 'observed trace cells; 64 token columns/page; decode initially', 'expert IDs, bytes, ns; ordinal layers/tokens'),
        'PREDICTION_META': _panel_meta(_source_refs(doc, 'expert-trace', 'engine-stats'), 'trace rows by session/phase; aggregates labelled separately', 'recall %, counts; KiB/MiB/GiB = 2^10/20/30 bytes'),
        'TIMELINE_META': _panel_meta(_source_refs(doc, 'expert-trace', 'engine-stats', 'run-summary'), 'measured decode tokens only; aggregate means not interpolated', 'ns, µs = 10^3 ns, ms = 10^6 ns'),
        'CHANGE_META': _panel_meta(_source_refs(doc, 'factory-store'), f'{len(doc["changes"])} linked component records; explicit references only', 'IDs, files, decision excerpt, A/B ratio'),
        'READ_METRICS': read_metrics, 'RECALL': recall_text, 'ACTUAL': _h(pregate.get('actual')),
        'COMPLETION': html.escape(completion), 'ARRIVAL': html.escape(arrival),
        'WAIT': _ms(totals['demand_wait_ns']), 'WAIT_MEAN': _ms(totals['demand_wait_ns_per_token']),
        'JOIN_WAIT': _ms(totals['join_wait_ns']), 'JOIN_COUNT': _h(totals['join_waits']), 'JOIN_BYTES': _bytes(totals['join_bytes']),
        'THREADS': thread_json, 'CHANGES': _changes(doc), 'SOURCES': sources, 'NOTES': notes,
        'SAMPLING': _h(provenance['sampling']), 'STATS': stats_json, 'DATA': serialized,
        'CSS': CSS, 'JS': JS,
    }
    # One substitution pass prevents evidence containing a template marker from
    # being interpreted as a second template instruction.
    import re
    return re.sub(r'__([A-Z_]+?)__', lambda m: replacements[m[1]], html_page)


CSS = r'''
:root {color-scheme:light dark;--bg:#f3f5f7;--panel:#fff;--ink:#1d2739;--muted:#526176;--line:#d4dce7;--resident:#269c78;--prefetched:#397cd5;--inflight:#dd791a;--queued:#b99718;--missing:#cc4b60;--unknown:#8b97a6;--residual:#bbc5d7}
@media(prefers-color-scheme:dark){:root{--bg:#101722;--panel:#192331;--ink:#e5edf9;--muted:#a7b5c8;--line:#344458;--resident:#49c59d;--prefetched:#6ca5f4;--inflight:#ffa854;--queued:#dbc462;--missing:#f27c8e;--unknown:#67768b;--residual:#56687f}}
:root[data-theme=light]{color-scheme:light;--bg:#f3f5f7;--panel:#fff;--ink:#1d2739;--muted:#526176;--line:#d4dce7;--unknown:#8b97a6;--residual:#bbc5d7}
:root[data-theme=dark]{color-scheme:dark;--bg:#101722;--panel:#192331;--ink:#e5edf9;--muted:#a7b5c8;--line:#344458;--unknown:#67768b;--residual:#56687f}
*{box-sizing:border-box}body{margin:0;padding:18px 22px;background:var(--bg);color:var(--ink);font:13px/1.45 system-ui,sans-serif}header{display:flex;justify-content:space-between;gap:12px;align-items:center}h1{font-size:22px;margin:0;overflow-wrap:anywhere}h2{font-size:16px;margin:0 0 5px}.eyebrow{font-size:10px;letter-spacing:.12em;color:var(--muted);margin:0 0 4px}p{margin:7px 0}small,.caption,.panel-meta{font-size:11px;color:var(--muted)}small{display:block}.badge{display:inline-block;padding:2px 7px;border:1px solid var(--line);border-radius:4px;font-size:10px}.tools,.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center}button,select{font:inherit;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:5px;padding:5px 8px}button{cursor:pointer}button:disabled{opacity:.4;cursor:default}code,pre{font:11px/1.45 ui-monospace,monospace;overflow-wrap:anywhere;white-space:pre-wrap}pre{max-height:240px;overflow:auto;margin:6px 0}.provenance{padding:9px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:9px 0;overflow-wrap:anywhere}.phases{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0}.phases>div{border:1px solid var(--line);border-radius:7px;padding:8px 12px;background:var(--panel)}.phases b{font-size:10px;letter-spacing:.08em;color:var(--muted)}.phases strong{font-size:17px;margin-left:12px}.controls{margin:12px 0}.controls label{font-size:11px;color:var(--muted)}main{display:grid;grid-template-columns:minmax(0,1.12fr) minmax(0,1fr);gap:12px}section{border:1px solid var(--line);border-radius:8px;padding:12px;background:var(--panel);min-width:0}.panel-meta{margin:2px 0 8px}.legend{display:flex;flex-wrap:wrap;gap:5px 12px;font-size:9px}.legend span{display:flex;align-items:center;gap:4px}.legend i{width:10px;height:8px;display:inline-block}.state-resident{fill:var(--resident);background:var(--resident)}.state-prefetched_done{fill:var(--prefetched);background:var(--prefetched)}.state-inflight{fill:var(--inflight);background:var(--inflight)}.state-queued{fill:var(--queued);background:var(--queued)}.state-missing{fill:var(--missing);background:var(--missing)}.state-unknown{fill:var(--unknown);background:var(--unknown)}.map{margin:8px 0;max-height:390px;overflow:auto}.map svg{width:100%;min-width:480px;display:block}.axis{font:8px ui-monospace,monospace;fill:var(--muted)}g[data-event]{cursor:pointer}g[data-event]:focus{outline:1px solid var(--ink)}g[data-event]:hover rect{stroke:var(--ink);stroke-width:.35}.cell-detail{font-size:10px;max-height:110px;min-height:55px;border-top:1px solid var(--line);padding-top:6px}.empty{min-height:95px;display:flex;align-items:center;justify-content:center;flex-direction:column;color:var(--muted);border:1px dashed var(--line);border-radius:6px;padding:14px;margin:8px 0;text-align:center;font-size:17px}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.metric{border-left:2px solid var(--line);padding-left:7px}.metric span{font-size:10px;color:var(--muted);display:block}.metric strong{font-size:15px;display:block}.metric small{font-size:9px}.table-wrap{overflow:auto;max-height:230px}table{width:100%;border-collapse:collapse;font-size:10px;text-align:left}th,td{padding:5px 6px;border-bottom:1px solid var(--line);vertical-align:top}th{position:sticky;top:0;background:var(--panel);font-weight:600}td small{font-size:9px}.timeline{max-height:185px;overflow:auto}.timeline svg{width:100%;min-width:400px}.changes{padding:0 0 0 18px;max-height:270px;overflow:auto}.changes li{padding:0 3px 10px 2px;border-bottom:1px solid var(--line);margin-bottom:9px}.changes p{font-size:11px}.changes code{font-size:10px}.changes small{font-size:10px}details{margin:9px 0}summary{cursor:pointer;color:var(--muted);font-size:11px}footer{margin:12px 0;font-size:11px}footer details{background:var(--panel);padding:9px 12px;border:1px solid var(--line);border-radius:7px}.sources{display:grid;grid-template-columns:1fr 1fr;gap:10px 25px;padding-left:20px}.sources li{overflow-wrap:anywhere;font-size:10px}footer ul{padding-left:17px}#page-note{font-size:10px;color:var(--muted)}@media(max-width:900px){main{grid-template-columns:1fr}.phases{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}.sources{grid-template-columns:1fr}body{padding:12px}.phases strong{font-size:15px}}@media print{.tools,.controls{display:none}body{padding:0}section{break-inside:avoid}.map,.table-wrap,.changes,.timeline{max-height:none}}
'''


JS = r'''
(() => {
'use strict';
const data=JSON.parse(document.getElementById('activity-data').textContent);
const byId=id=>document.getElementById(id), events=data.activity.events;
const unknown=v=>v===null||v===undefined;
const text=v=>unknown(v)?'UNKNOWN':typeof v==='object'?JSON.stringify(v):String(v);
const ms=v=>unknown(v)?'UNKNOWN':v>0&&v<1000?v+' ns':v>=1000&&v<1e6?(v/1000).toFixed(3)+' µs':(v/1e6).toLocaleString(undefined,{maximumFractionDigits:3})+' ms';
const gib=v=>{if(unknown(v))return 'UNKNOWN';for(const [power,unit] of [[30,'GiB'],[20,'MiB'],[10,'KiB']])if(v>=2**power)return (v/2**power).toFixed(3)+' '+unit;return v+' bytes';};
const el=(tag,content)=>{const e=document.createElement(tag);if(content!==undefined)e.textContent=content;return e;};
const svg=(tag,attrs={})=>{const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,v);return e;};
const svgText=(root,x,y,value)=>{const e=svg('text',{x,y,class:'axis'});e.textContent=value;root.append(e);};
const detail=e=>[
 `Run ${e.run_id} · ${e.phase} token ${e.token_idx} · layer ${e.layer}`,
 `Selected IDs: ${text(e.selected_ids)} · predicted IDs: ${text(e.predicted_ids)}`,
 `Prediction source: ${text(e.prediction_source)}`,
 'Readiness at arrival: '+(e.readiness.length?e.readiness.map(x=>`${x.expert_id}:${x.class.toUpperCase()} (resident ${text(x.resident_bytes)}/${text(x.required_bytes)} bytes)`).join(', '):'UNKNOWN'),
 `Demand read ${text(e.demand_read_bytes)} bytes · demand wait ${text(e.demand_wait_ns)} ns`,
 'Speculative bytes: '+Object.entries(e.speculative).map(([k,v])=>k+'='+text(v)).join(', '),
 `Arrival ${text(e.arrival_ns)} ns · fill end ${text(e.fill_end_ns)} ns (monotonic)`,
 `Join ${text(e.join_waits)} waits, ${text(e.join_wait_ns)} ns, ${text(e.join_bytes)} bytes`,
 `Source: ${e.source}`].join('\n');
function empty(target,label){const box=el('div',label);box.className='empty';target.replaceChildren(box);}
for(const session of data.activity.sessions)byId('session').append(new Option(session,session));
if(!data.activity.sessions.length)byId('session').append(new Option('UNKNOWN — no trace',''));
let page=0;
const session=()=>byId('session').value, phase=()=>byId('phase').value;
function current(){return events.map((e,i)=>({e,i})).filter(x=>x.e.run_id===session()&&x.e.phase===phase());}
function tokenList(rows){const observed=[...new Set(rows.map(x=>x.e.token_idx))].sort((a,b)=>a-b);
 // Show small internal gaps as UNKNOWN; do not claim unobserved start/end bounds.
 if(observed.length&&observed.at(-1)-observed[0]<256)return Array.from({length:observed.at(-1)-observed[0]+1},(_,i)=>i+observed[0]);
 return observed;}
function map(){
 const target=byId('map'),rows=current(),allTokens=tokenList(rows),tokens=allTokens.slice(page*64,(page+1)*64);
 byId('previous').disabled=page===0;byId('next').disabled=(page+1)*64>=allTokens.length;
 byId('page-note').textContent=`${rows.length} observed ${phase()} rows · ${allTokens.length?`columns ${page*64+1}–${Math.min((page+1)*64,allTokens.length)} of ${allTokens.length}`:'per-token coverage UNKNOWN'}; no averaging`;
 if(!rows.length){empty(target,phase()==='load'?'Load: no expert routing tokens; see separate phase totals':'UNKNOWN — aggregate, no per-token trace for this session/phase');return;}
 const meta=data.activity.metadata[session()]||{},n=meta.n_layers||data.model.n_layers;
 const layers=n?Array.from({length:n},(_,i)=>i):[...new Set(rows.map(x=>x.e.layer))].sort((a,b)=>a-b);
 const width=Math.max(480,tokens.length*12+44),height=Math.max(80,layers.length*10+32),dx=(width-44)/Math.max(1,tokens.length);
 const root=svg('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':'Layer by token expert activity map'});
 const index=new Map(rows.map(x=>[`${x.e.layer}/${x.e.token_idx}`,x]));
 tokens.forEach((t,c)=>{if(c%4===0)svgText(root,40+c*dx,12,t);});
 layers.forEach((l,r)=>{const y=22+r*10;svgText(root,2,y+7,'L'+l);tokens.forEach((t,c)=>{
   const x=40+c*dx,item=index.get(`${l}/${t}`),states=item&&item.e.readiness.length?item.e.readiness.map(s=>s.class):['unknown'];
   const group=svg('g',item?{'data-event':item.i,tabindex:0,role:'button','aria-label':`Layer ${l}, token ${t}: expert details`}:{});
   const title=svg('title');title.textContent=item?detail(item.e):'Unobserved layer/token: UNKNOWN';group.append(title);
   states.forEach((state,s)=>group.append(svg('rect',{x:x+s*(dx-1)/states.length,y,width:(dx-1)/states.length,height:8,class:'state-'+state})));
   root.append(group);
 });});target.replaceChildren(root);
}
function predictions(){
 const target=byId('prediction-table'),rows=data.predictions.filter(r=>r.run_id===session()&&r.phase===phase());
 const cells=current().map(x=>x.e),sum=values=>values.length&&values.every(v=>!unknown(v))?values.reduce((a,b)=>a+b,0):null;
 const demand=sum(cells.map(e=>e.demand_read_bytes)),spec=key=>sum(cells.map(e=>e.speculative[key]));
 const scopes=[...new Set(cells.map(e=>e.speculative.unused_scope).filter(Boolean))];
 byId('trace-totals').textContent=`Observed ${phase()} cells only (${cells.length} rows; no extrapolation): demand ${gib(demand)}; speculative issued ${gib(spec('issued_bytes'))}, read ${gib(spec('read_bytes'))}, used ${gib(spec('used_bytes'))}, unused ${gib(spec('wasted_bytes'))} (scope: ${scopes.join(', ')||'UNKNOWN'}).`;
 if(!rows.length){empty(target,'Per-layer recall / timely / late / unused: UNKNOWN');return;}
 const table=el('table'),thead=el('thead'),tr=el('tr');
 ['Layer','Recall / coverage','Ready / late hits','Spec issued / read','Spec used / unused'].forEach(v=>tr.append(el('th',v)));thead.append(tr);table.append(thead);
 const body=el('tbody');for(const r of rows){const row=el('tr');
 row.append(el('td','L'+r.layer));
 let cell=el('td',unknown(r.recall)?'UNKNOWN':(r.recall*100).toFixed(1)+'%');cell.append(el('small',`${text(r.hits)}/${text(r.selected_count)} selected IDs; ${r.compared_records}/${r.records} records`));row.append(cell);
 cell=el('td',`${text(r.timely_selected)} / ${text(r.late_selected)}`);cell.append(el('small','selected predicted IDs; readiness at arrival'));row.append(cell);
 cell=el('td',`${gib(r.speculative.issued_bytes)} / ${gib(r.speculative.read_bytes)}`);cell.append(el('small',`timely ${gib(r.speculative.timely_bytes)}; late ${gib(r.speculative.late_bytes)}`));row.append(cell);
 cell=el('td',`${gib(r.speculative.used_bytes)} / ${gib(r.speculative.wasted_bytes)}`);cell.append(el('small','unused scope: '+(r.unused_scopes.join(', ')||'UNKNOWN')));row.append(cell);body.append(row);
 }table.append(body);target.replaceChildren(table);
}
function timeline(){
 const target=byId('timeline');if(phase()!=='decode'){empty(target,'Decode timeline only; other phases have separate totals.');return;}
 const all=data.timeline.filter(r=>r.run_id===session()), tokenSet=new Set(tokenList(current()).slice(page*64,(page+1)*64));
 const rows=all.filter(r=>tokenSet.size?tokenSet.has(r.token_idx):true).slice(0,64);
 if(!rows.length){empty(target,'Per-token demand wait versus rest: UNKNOWN — no token timing trace');return;}
 const known=rows.flatMap(r=>[r.token_duration_ns,r.demand_wait_ns,r.measured_layer_wait_ns]).filter(v=>!unknown(v));
 if(!known.length){empty(target,'Per-token demand wait and duration UNKNOWN — selected-only trace');return;}
 const maximum=Math.max(...known,1),width=680,barWidth=360,root=svg('svg',{viewBox:`0 0 ${width} ${rows.length*19+25}`,role:'img','aria-label':'Decode demand wait and inferred residual wall time'});
 svgText(root,54,10,'main-thread demand wait → inferred residual; UNKNOWN shown explicitly');
 rows.forEach((r,i)=>{const y=19+i*19;svgText(root,2,y+8,'t'+r.token_idx);const group=svg('g'),title=svg('title');
  title.textContent=`Token ${r.token_idx}: wait ${ms(r.demand_wait_ns)}, measured layer subset ${ms(r.measured_layer_wait_ns)} (${r.measured_layers}/${text(r.expected_layers)} layers), duration ${ms(r.token_duration_ns)}, rest ${ms(r.rest_ns)} (${r.rest_attribution}); source ${r.source}`;
  group.append(title);const duration=r.token_duration_ns,wait=r.demand_wait_ns,partial=unknown(wait)?r.measured_layer_wait_ns:wait;
  if(!unknown(duration))group.append(svg('rect',{x:54,y,width:barWidth*duration/maximum,height:10,fill:unknown(r.rest_ns)?'var(--unknown)':'var(--residual)'}));
  if(!unknown(partial))group.append(svg('rect',{x:54,y,width:barWidth*partial/maximum,height:10,fill:'var(--inflight)',opacity:unknown(wait)?.6:1}));
  root.append(group);svgText(root,424,y+8,`${ms(wait)} wait / ${ms(r.rest_ns)} rest${unknown(wait)&&!unknown(partial)?' (partial '+ms(partial)+')':''}${r.timing_consistent?'':' — inconsistent timing'}`);
 });target.replaceChildren(root);
}
function refresh(){map();predictions();timeline();byId('cell-detail').textContent='Select a cell for exact IDs, readiness, bytes, wait and provenance.';}
byId('session').addEventListener('change',()=>{page=0;refresh();});byId('phase').addEventListener('change',()=>{page=0;refresh();});
byId('previous').addEventListener('click',()=>{page=Math.max(0,page-1);refresh();});byId('next').addEventListener('click',()=>{page++;refresh();});
for(const type of ['click','mouseover','focusin','keydown'])byId('map').addEventListener(type,event=>{
 if(type==='keydown'&&!['Enter',' '].includes(event.key))return;
 const group=event.target.closest('[data-event]');if(group)byId('cell-detail').textContent=detail(events[Number(group.dataset.event)]);
});
byId('theme').addEventListener('click',()=>{const dark=document.documentElement.dataset.theme?document.documentElement.dataset.theme==='dark':matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.dataset.theme=dark?'light':'dark';});
byId('download').addEventListener('click',()=>{const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=el('a');a.href=url;a.download='expert-activity.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
refresh();
})();
'''
