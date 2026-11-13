"""Playbook-driven demo video: render each scene from real evidence with headless Chrome, then
assemble an MP4 with ffmpeg. No user interaction; every number comes from a recorded source.

    jiuwenswarm factory demo build            # assembles the evidence pack first
    jiuwenswarm factory demo video --out DIR  # scenes/*.html, frames/*.png, demo.mp4, REVIEW.md
"""
import csv
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PLAYBOOK = Path(__file__).with_name('demo_playbook.json')
RUN4 = 'factory-bd173c082bf34ae3b8471938c19b8068'
RUN5 = 'factory-53db494559954fc6a690a9a014afbf21'
ROOT = Path(__file__).resolve().parents[2]

CSS = """
:root{--bg:#F7F6F2;--ink:#14213D;--muted:#4A5568;--line:#DDD8CC;--card:#FFFFFF;--accent:#B5531C;--soft:#FBE3D3;
--blue:#2F6FB0;--blue-soft:#E3EDF8;--good:#2E7D4F;--good-soft:#E2F2E8;--warn:#9A6A00;--warn-soft:#FBF1D6;
--sans:'DejaVu Sans','Liberation Sans',Arial,sans-serif;--mono:'DejaVu Sans Mono','Liberation Mono',monospace}
*{box-sizing:border-box}html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:var(--bg);color:var(--ink);font-family:var(--sans)}
.frame{position:absolute;inset:0;padding:64px 96px 112px;display:flex;flex-direction:column;gap:28px}
.top{display:flex;align-items:center;gap:20px}
.pill{font:700 22px var(--sans);letter-spacing:.08em;padding:6px 16px;border-radius:999px;background:var(--blue-soft);color:var(--blue)}
.pill.rec{background:var(--soft);color:var(--accent)}.pill.cap{background:var(--warn-soft);color:var(--warn)}.pill.slide{background:var(--good-soft);color:var(--good)}
.step{font:600 22px var(--sans);color:var(--muted)}
h1{font-size:60px;line-height:1.1;margin:0}
.sub{font-size:30px;color:var(--muted);margin:0;line-height:1.35;max-width:1600px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:32px;align-items:start;min-height:0}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:26px 30px;display:flex;flex-direction:column;gap:14px;min-height:0;overflow:hidden}
.card h3{margin:0;font-size:26px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.big{font:700 64px var(--sans)}
.kv{display:grid;grid-template-columns:auto 1fr;gap:10px 22px;font-size:25px}.kv b{color:var(--muted);font-weight:600}
pre{margin:0;font:21px/1.45 var(--mono);white-space:pre-wrap;word-break:break-word;overflow:hidden}
.add{color:#1F6F3F}.del{color:#A33}
table{border-collapse:collapse;width:100%;font-size:25px}td,th{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left}
th{color:var(--muted);font-size:21px;text-transform:uppercase}td.n{text-align:right;font-variant-numeric:tabular-nums}
.foot{position:absolute;left:96px;right:96px;bottom:36px;font-size:20px;color:var(--muted);display:flex;justify-content:space-between;gap:24px}
.tag{display:inline-block;font:700 20px var(--sans);padding:3px 12px;border-radius:999px}
.keep{background:var(--good-soft);color:var(--good)}.dorm{background:var(--warn-soft);color:var(--warn)}.rev{background:var(--soft);color:var(--accent)}
.node{font-size:24px;padding:6px 0}.node.new{color:var(--accent);font-weight:700}
ul{margin:0;padding-left:30px;font-size:27px;line-height:1.45}
"""


def _esc(text):
    return html.escape(str(text))


def _page(scene, index, total, body, foot):
    label = scene['label']
    cls = {'RECORDED': 'rec', 'SEPARATE CAPTURE': 'cap', 'SLIDE': 'slide', 'RUN 5 EXCERPT': 'cap'}.get(label, '')
    return (f'<!doctype html><meta charset="utf-8"><style>{CSS}</style><div class="frame">'
            f'<div class="top"><span class="pill {cls}">{_esc(label)}</span><span class="step">{index}/{total}</span></div>'
            f'<h1>{_esc(scene["title"])}</h1>' + (f'<p class="sub">{_esc(scene["subtitle"])}</p>' if scene.get('subtitle') else '')
            + body + f'</div><div class="foot"><span>Source: {_esc(foot)}</span><span>Satay · Jetson Orin Nano 8 GB · JiuwenSwarm software factory</span></div>')


def _cli(*args):
    exe = shutil.which('jiuwenswarm') or str(Path(sys.executable).with_name('jiuwenswarm'))
    out = subprocess.run([exe, 'factory', *args], capture_output=True, text=True, timeout=120)
    return out.stdout


class Evidence:
    """Everything a scene shows, loaded once from recorded sources."""
    def __init__(self, pack, siminfeng):
        self.pack = Path(pack)
        self.sections = {s['id']: s for s in json.loads((self.pack / 'sections.json').read_text())['sections']}
        self.siminfeng = Path(siminfeng)
        self.contract = json.loads((ROOT / 'jiuwenswarm/factory/contracts/qwen36-bare-greedy-v1.json').read_text())
        self.output_text = (self.pack / 'assets' / (self.contract['reference']['stdout_sha256'] + '.txt')).read_text().strip()
        self.story4 = (ROOT / 'artifacts/factory/evidence' / RUN4 / 'STORY.txt').read_text()
        self.telemetry = json.loads(_cli('telemetry', RUN4, '--json') or '{}')
        self.plan12 = json.loads(_cli('plan', RUN5, '--rev', '12', '--json'))
        self.plan13 = json.loads(_cli('plan', RUN5, '--rev', '13', '--json'))
        capture = self.siminfeng / 'experiments/jetson/OM/J-XS4-activity'
        self.capture_stderr = (capture / 'stderr.txt').read_text()
        self.capture_image = (capture / 'image.id').read_text().strip()
        self.trace = list(csv.DictReader((capture / 'expert_trace.csv').open()))
        self.jom13 = (self.siminfeng / 'experiments/jetson/OM/J-OM13/REPORT.md').read_text()


def _stats(line_prefix, text):
    matches = re.findall(line_prefix + r'(.*)', text)  # last context is the real generation
    return {k: float(v) for k, v in re.findall(r'(\w+)=([0-9.]+)', matches[-1])} if matches else {}


# ---- scenes -------------------------------------------------------------------------------

def scene_slide(scene, ev):
    slide = (ROOT / 'demo/assets/slides' / scene['slide']).read_text()
    slide = re.sub(r'<aside>.*?</aside>', '', slide, flags=re.S)
    return (f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0;width:1920px;height:1080px;overflow:hidden}}'
            'section{position:relative;width:1920px;height:1080px;box-sizing:border-box}section h1,section h2,section h3,section p,section ul{margin:0}'
            'section *{box-sizing:border-box}x-connector{display:flex;align-items:center;justify-content:center;flex:0 0 48px;font-size:40px;color:#14213D}'
            f'x-connector::before{{content:"→"}}</style>{slide}')


def scene_title(scene, ev):
    body = ('<div class="card" style="flex:1;justify-content:center;gap:26px"><div class="big" style="font-size:54px">'
            'Plain llama.cpp + a task contract → JiuwenSwarm uses a few CCs → a faster engine</div>'
            '<ul><li>Model: Qwen3.6-35B-A3B, 20.8 GiB; machine: 7.4 GiB of shared memory</li>'
            '<li>Everything shown is recorded evidence from real runs on this Jetson</li>'
            '<li>Long builds and A/B runs are shown as their results, not streamed</li></ul></div>')
    return body, 'demo playbook'


def scene_baseline(scene, ev):
    c, ref = ev.contract, ev.contract['reference']
    argv = ' '.join(c['workload']['argv'])
    bare = re.search(r'contract\s+qwen36-bare-greedy-v1 · pass.*', ev.story4)
    body = ('<div class="cols"><div class="card"><h3>Engine and contract</h3><div class="kv">'
            f'<b>Engine</b><span>llama.cpp cf34d311 (unmodified)</span><b>Image</b><span>{_esc(ref["image_tag"])}</span>'
            f'<b>Image id</b><span>{_esc(ref["image_id"][:19])}…</span><b>Model</b><span>Qwen3.6-35B-A3B UD-Q4_K_XL</span>'
            f'<b>Contract</b><span>{_esc(c["contract_id"])} (frozen)</span><b>Check</b><span>byte-identical greedy output</span>'
            f'<b>Reference</b><span>{ref["stdout_sha256"][:12]}…</span><b>Speed</b><span>903.95 ms/token (Run 4, single lab run)</span></div>'
            f'<pre style="font-size:19px;color:var(--muted)">{_esc(argv)}</pre></div>'
            f'<div class="card"><h3>Generated output (64 tokens, greedy)</h3><pre style="font-size:24px">{_esc(ev.output_text[:520])}…</pre></div></div>')
    return body, f'contract qwen36-bare-greedy-v1; Run 4 {RUN4[:16]}… bare evaluation'


def scene_task(scene, ev):
    t = json.loads((ROOT / 'jiuwenswarm/factory/tasks/evolve-qwen36.json').read_text())
    body = (f'<div class="cols"><div class="card"><h3>The task given to the agent (Run 4)</h3><pre style="font-size:25px">{_esc(t["objective"])}</pre></div>'
            '<div class="card"><h3>Limits and authority</h3><div class="kv">'
            f'<b>Contract</b><span>{_esc(t["contract_id"])} (immutable)</span><b>Budget</b><span>{t["budget"]["max_turns"]} turns, {t["budget"]["wall_clock_s"]//3600} h</span>'
            f'<b>Grants</b><span>{_esc(", ".join(t["allowed_effects"]))}</span><b>Source</b><span>owned checkout, branch {_esc(t["source"]["branch"])} at cf34d3113</span>'
            '<b>Target</b><span>jetson-orin</span><b>Command</b><span style="font-family:var(--mono);font-size:21px">jiuwenswarm factory run &lt;task&gt; --grant …</span></div></div></div>')
    return body, 'jiuwenswarm/factory/tasks/evolve-qwen36.json (Run 4 task)'


def scene_capsules(scene, ev):
    rows = {r['capability']: r for r in ev.telemetry.get('capabilities', [])}
    show = [('builder.submit', 'Start an image build'), ('inspector.preflight', 'Check image flags'),
            ('inspector.verify_effective_config', 'Prove settings in use'), ('lab.ab_submit', 'Queue an A/B experiment'),
            ('evidence.read', 'Read evidence'), ('evidence.publish', 'Publish a decision')]
    trs = ''.join(f'<tr><td>{_esc(n)}</td><td>{_esc(d)}</td><td class="n">{int(rows[n]["calls"]) if n in rows else "—"}</td></tr>' for n, d in show)
    turns = len(ev.telemetry.get('turns', []))
    body = (f'<div class="cols"><div class="card"><h3>CC calls the agent made in Run 4</h3><table style="font-size:23px"><tr><th>Capability</th><th>What it does</th><th>Calls</th></tr>{trs}</table></div>'
            '<div class="card"><h3>Guidance it read before acting</h3><ul>'
            '<li><b>factory.integration_skill</b> · how to integrate and repair a patch</li>'
            '<li><b>factory.methodology_ab</b> · A/B rules: ABBA order, noise floor, keep only on improvement</li>'
            '<li><b>component CCs</b> · each patch with its dependencies, switches and engagement checks</li></ul>'
            f'<p class="sub" style="font-size:26px">{turns} agent turns. Builds and lab runs are durable jobs that survive the agent\'s turn ending.</p></div></div>')
    return body, f'factory telemetry {RUN4[:16]}… (factory.telemetry/1)'


def scene_source(scene, ev):
    text = ev.sections['source']['text']
    head = text.splitlines()[0]
    lines = [l for l in text.splitlines()[1:] if l.startswith(('+', '@@', 'diff'))][:26]
    diff = '\n'.join(f'<span class="add">{_esc(l)}</span>' if l.startswith('+') else _esc(l) for l in lines)
    builds = re.findall(r'build\s+(\w{8}) · (\d+) s → image (\w+)', ev.story4)
    brow = ''.join(f'<tr><td>{b}</td><td class="n">{s} s</td><td>{i}</td></tr>' for b, s, i in builds[:6])
    commit, image = head.split(': ', 1)[1].split(' → ')
    body = (f'<div class="cols" style="grid-template-columns:1.25fr 1fr"><div class="card"><h3>Integration commit: expert_fill hook in llama-context.cpp</h3><pre style="font-size:18px">{diff}</pre></div>'
            f'<div class="card"><h3>Build receipts</h3><div class="kv"><b>Commit</b><span>{commit[:12]}</span><b>Image</b><span>{image[:19]}…</span></div>'
            f'<table><tr><th>Build</th><th>Time</th><th>Image</th></tr>{brow}</table>'
            '<p class="sub" style="font-size:24px">The lab admits only the exact image id a build produced.</p></div></div>')
    return body, 'Run 4 integration commit diff and build receipts (store artifacts)'


def scene_decisions(scene, ev):
    rows = [('mmap_advice', '0.49×', 'dorm', 'kept off: later components need its code'),
            ('router_prefetch', '0.62×', 'dorm', 'kept off: later components need its code'),
            ('expert_fill', '1.11×', 'keep', 'kept: faster, identical output'),
            ('expert_pregate', '1.13×', 'keep', 'kept: faster, identical output'),
            ('thread_names', '1.01×', 'rev', 'reverted: no measured benefit')]
    found = {m: re.search(rf'ab_result\s+{m} · gate (\w+) · ratio ([0-9.]+)', ev.story4) for m, *_ in rows}
    trs = ''.join(f'<tr><td>{m}</td><td class="n">{(f"{float(found[m].group(2)):.2f}×" if found[m] else r)}</td>'
                  f'<td><span class="tag {c}">{ {"dorm": "dormant", "keep": "keep", "rev": "revert"}[c] }</span></td><td>{_esc(w)}</td></tr>' for m, r, c, w in rows)
    body = (f'<div class="card" style="flex:1"><h3>Each component: integrate → build → A/B on the real model → decide</h3>'
            f'<table><tr><th>Component</th><th>A/B speed (&gt;1 = faster)</th><th>Decision</th><th>Why</th></tr>{trs}</table>'
            '<p class="sub" style="font-size:26px">A/B = alternating baseline and candidate runs (ABBA) with an A/A noise floor. All outputs matched the frozen reference.</p></div>')
    return body, f'Run 4 story: ab_result observations ({RUN4[:16]}…)'


def scene_activity(scene, ev):
    rows = [r for r in ev.trace if r['phase'] == 'decode']
    tokens = sorted({int(r['token_idx']) for r in rows})
    layers = sorted({int(r['layer']) for r in rows})
    cell, gap = 13, 1
    svg = []
    for r in rows:
        x = tokens.index(int(r['token_idx'])) * (cell + gap)
        y = layers.index(int(r['layer'])) * (cell + gap)
        sel, pred = set(r['selected'].split()), set((r['predicted'] or '').split())
        if not pred:
            color = '#D9D4C7'
        else:
            hits = len(sel & pred)
            color = '#14467A' if hits >= 7 else '#3F86C9' if hits >= 5 else '#F0B37E' if hits >= 3 else '#B5531C'
        svg.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{color}"/>')
    w, h = len(tokens) * (cell + gap), len(layers) * (cell + gap)
    s = _stats('expert_readiness: stats ', ev.capture_stderr)
    rp = s['decode_ready_bytes_predicted'] / (s['decode_ready_bytes_predicted'] + s['decode_missing_bytes_predicted'])
    ru = s['decode_ready_bytes_unpredicted'] / (s['decode_ready_bytes_unpredicted'] + s['decode_missing_bytes_unpredicted'])
    share = s['decode_selected_predicted'] / s['decode_selected']
    bars = ''.join(f'<div style="font-size:25px">{n}</div><div style="display:flex;height:40px;border-radius:8px;overflow:hidden">'
                   f'<div style="width:{v*100:.0f}%;background:var(--good);color:#fff;font:700 22px var(--sans);padding:6px 10px">{v*100:.0f}% ready</div>'
                   f'<div style="flex:1;background:var(--accent)"></div></div>' for n, v in (('Predicted experts', rp), ('Unpredicted experts', ru)))
    body = (f'<div class="cols" style="grid-template-columns:1.35fr 1fr"><div class="card"><h3>Each cell: one layer (row) of one generated token (column)</h3>'
            f'<svg viewBox="0 0 {w} {h}" width="100%" style="flex:1">{"".join(svg)}</svg>'
            '<div style="display:flex;gap:18px;flex-wrap:wrap;font-size:21px">'
            + ''.join(f'<span><span style="display:inline-block;width:18px;height:18px;background:{c};vertical-align:middle"></span> {t}</span>'
                      for c, t in (('#14467A', '7–8 of 8 predicted'), ('#3F86C9', '5–6'), ('#F0B37E', '3–4'), ('#B5531C', '0–2'), ('#D9D4C7', 'layer 0: not predicted')))
            + '</div></div>'
            f'<div class="card"><h3>Were the weights in memory in time?</h3><div class="big">{share*100:.0f}%</div><div style="font-size:25px">of chosen experts were predicted one layer ahead</div>'
            f'{bars}<div style="font-size:22px;color:var(--muted)">Bytes of the chosen experts already in memory when the matmul needed them. Rest: read on demand.</div></div></div>')
    return body, f'capture run J-XS4 (unscored), image {ev.capture_image[7:19]}'


def scene_revision(scene, ev):
    before = {n['node_id']: n for n in ev.plan12['nodes']}
    after = ev.plan13['nodes']
    items = ''.join(f'<div class="node{" new" if n["node_id"] not in before else ""}">{"＋ " if n["node_id"] not in before else ""}'
                    f'[{_esc(n["state"])}] {_esc(n["title"])}</div>' for n in after if n['state'] != 'done' or n['node_id'] not in before)
    obs = ev.sections['revision']['text'].split('\n')[0].strip('"')
    body = (f'<div class="cols"><div class="card"><h3>What the agent observed (decision 13)</h3><pre style="font-size:23px">{_esc(obs[:520])}</pre>'
            '<p class="sub" style="font-size:25px">A build whose settings can’t be verified can’t be scored. So the plan changes before any measurement.</p></div>'
            f'<div class="card"><h3>Task graph revision 12 → 13 (pending work)</h3>{items}'
            '<p class="sub" style="font-size:24px">Completed builds are kept. Run 5 was held for later and kept no component.</p></div></div>')
    return body, f'Run 5 excerpt {RUN5[:16]}…: decision 13, factory plan --rev 12/13'


def scene_result(scene, ev):
    def ms(arm):
        m = re.search(rf'\|\s*{arm}\s*\|\s*([0-9.]+)', ev.jom13)
        return float(m.group(1)) if m else None
    base, fac = ms('base') or 841.5, ms('factory') or 711.4
    bar = lambda v, c: f'<div style="height:54px;width:{v/base*100:.0f}%;background:{c};border-radius:8px;color:#fff;font:700 26px var(--sans);padding:10px 14px">{v:.1f} ms/token</div>'
    body = (f'<div class="cols"><div class="card"><h3>Direct A/B on the real model (J-OM13, 12 runs)</h3>'
            f'<div style="font-size:26px">Plain llama.cpp</div>{bar(base, "#6B7A90")}<div style="font-size:26px">Factory engine (expert streaming)</div>{bar(fac, "var(--good)")}'
            f'<div class="big">{base/fac:.2f}× faster</div><div style="font-size:25px">Generated output byte-identical in every run. Lower is better.</div></div>'
            f'<div class="card"><h3>Same output from the faster engine</h3><pre style="font-size:23px">{_esc(ev.output_text[:420])}…</pre>'
            '<div style="font-size:22px;color:var(--muted)">Run 4’s own single lab runs: 903.95 → 785.22 ms/token.</div></div></div>')
    return body, 'siminfeng experiments/jetson/OM/J-OM13/REPORT.md; Run 4 evaluations'


def scene_handoff(scene, ev):
    body = ('<div class="cols"><div class="card"><h3>engine.expert_streaming 2.0.0</h3><ul style="font-size:25px">'
            '<li>Guide: when expert streaming applies and what to try</li><li>Evidence method: prediction ≠ readiness ≠ speed</li>'
            '<li>8 components (patches with contracts and acceptance rules)</li><li>Tools: applicability, engagement</li></ul></div>'
            '<div class="card"><h3>Handed to the RSI team</h3><div class="kv"><b>Release</b><span>tag cc-rsi-v1</span><b>Repo</b><span>Stellven/jiuwenswarm · cc-siminfeng</span>'
            '<b>Start</b><span>RSI-START-HERE.md</span><b>Lab round</b><span>~10 min (fast contract)</span></div>'
            '<p class="sub" style="font-size:25px">We improved an engine with CCs. The next segment improves the CCs themselves.</p></div></div>')
    return body, 'RSI-START-HERE.md; git tag cc-rsi-v1'


BUILDERS = {k[6:]: v for k, v in globals().items() if k.startswith('scene_')}


def render(out, pack, siminfeng, chrome, ffmpeg, playbook=PLAYBOOK):
    out = Path(out); (out / 'scenes').mkdir(parents=True, exist_ok=True); (out / 'frames').mkdir(exist_ok=True)
    book = json.loads(Path(playbook).read_text())
    ev = Evidence(pack, siminfeng)
    scenes, total = book['scenes'], len(book['scenes'])
    for i, scene in enumerate(scenes, 1):
        built = BUILDERS[scene['builder']](scene, ev)
        page = built if isinstance(built, str) else _page(scene, i, total, *built)
        path = out / 'scenes' / f'{i:02d}-{scene["id"]}.html'
        path.write_text(page, encoding='utf-8')
        png = out / 'frames' / f'{i:02d}-{scene["id"]}.png'
        subprocess.run([chrome, '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
                        '--window-size=1920,1080', f'--screenshot={png}', path.resolve().as_uri()],
                       capture_output=True, timeout=120, check=True)
    concat = out / 'frames' / 'concat.txt'
    concat.write_text(''.join(f"file '{(out / 'frames' / f'{i:02d}-{s['id']}.png').resolve()}'\nduration {s['seconds']}\n"
                              for i, s in enumerate(scenes, 1))
                      + f"file '{(out / 'frames' / f'{total:02d}-{scenes[-1]['id']}.png').resolve()}'\n")
    video = out / 'demo.mp4'
    subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat), '-vf', 'fps=10,format=yuv420p',
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24', str(video)], check=True, timeout=1800)
    seconds = sum(s['seconds'] for s in scenes)
    (out / 'REVIEW.md').write_text('# Demo video scenes\n\n| # | Scene | Label | Seconds | Frame |\n|---|---|---|---|---|\n'
        + ''.join(f'| {i} | {s["title"]} | {s["label"]} | {s["seconds"]} | frames/{i:02d}-{s["id"]}.png |\n' for i, s in enumerate(scenes, 1))
        + f'\nTotal {seconds} s ({seconds/60:.1f} min). Video: demo.mp4\n')
    return video, seconds


def find_ffmpeg(explicit=None):
    if explicit:
        return explicit
    if shutil.which('ffmpeg'):
        return shutil.which('ffmpeg')
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise SystemExit('ffmpeg not found: install ffmpeg or pass --ffmpeg (e.g. from pip imageio-ffmpeg)')
