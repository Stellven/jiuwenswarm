"""Render the three still cards for the recorded demo video (1920x1080 PNG via headless Chrome).

    python docs/demo/cards.py OUTDIR results.json
results.json: {"plain_ms": .., "final_ms": .., "plain_tps": .., "final_tps": .., "status": "confirmed"|"preliminary",
               "contract": "...", "output": "...", "engagement": "...", "note": "..."}
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSS = """
body{margin:0;width:1920px;height:1080px;background:#15171c;color:#e6e6e6;font-family:Inter,'DejaVu Sans',sans-serif;
display:flex;flex-direction:column;justify-content:center;padding:0 120px;box-sizing:border-box}
h1{font-size:60px;margin:0 0 18px;font-weight:700}
.sub{font-size:30px;color:#9a9ea8;margin-bottom:40px}
.grey{color:#9a9ea8}.amber{color:#e0a040}.green{color:#7fd08a}
.tag{display:inline-block;font-size:24px;padding:6px 16px;border-radius:8px;border:2px solid currentColor;margin-left:16px;vertical-align:middle}
table{border-collapse:collapse;font-size:38px;margin:10px 0 30px}
td,th{padding:14px 40px 14px 0;text-align:left;font-variant-numeric:tabular-nums}
th{font-size:26px;color:#9a9ea8;font-weight:400}
.small{font-size:26px;color:#b8bcc6;line-height:1.5;max-width:1600px}
.cands{display:grid;grid-template-columns:repeat(3,1fr);gap:36px;margin-top:40px}
.cand{border:2px dashed #6a6e78;border-radius:14px;padding:30px;font-size:28px;line-height:1.4}
.cand b{display:block;font-size:32px;margin-bottom:12px}
.lbl{font-size:20px;letter-spacing:.12em;text-transform:uppercase;color:#9a9ea8}
"""


def page(body):
    return f'<!doctype html><meta charset="utf-8"><style>{CSS}</style><body>{body}</body>'


def cards(r):
    svg = (HERE / 'engine-diagram.svg').read_text()
    diagram = page('<h1 style="font-size:46px">Where the CC-guided changes plug into llama.cpp</h1>'
                   '<div class="sub" style="margin-bottom:20px;font-size:26px">Experts run on the CPU from memory-mapped weights. '
                   'The changes only make those weights arrive earlier; weights, kernels, router and sampling are unchanged.</div>'
                   f'<div style="width:1680px">{svg.replace("<svg ", "<svg style=\'width:100%;height:auto;font-size:15px\' ", 1)}</div>')
    status = r['status']
    label = ('<span class="tag green">CONFIRMED · ABBA</span>' if status == 'confirmed'
             else '<span class="tag" style="color:#e6e6e6">PRELIMINARY</span>')
    speed = r['plain_ms'] / r['final_ms']
    result = page(f'<div class="lbl">Measured result · {r["contract"]}</div>'
                  f'<h1>Faster engine, same output {label}</h1>'
                  '<table><tr><th></th><th>decode ms/token</th><th>tokens/s</th></tr>'
                  f'<tr class="grey"><td>plain llama.cpp</td><td>{r["plain_ms"]:.1f}</td><td>{r["plain_tps"]:.2f}</td></tr>'
                  f'<tr class="green"><td>factory engine</td><td>{r["final_ms"]:.1f}</td><td>{r["final_tps"]:.2f}</td></tr>'
                  f'<tr><td></td><td class="green">{speed:.2f}× faster per token</td><td></td></tr></table>'
                  f'<div class="small">Output: {r["output"]}<br>Engagement: {r["engagement"]}<br>{r["note"]}</div>')
    closing = page('<h1 style="font-size:54px">This capability is implemented and measured.<br>'
                   'What other engineering methods can we package?</h1>'
                   '<div class="lbl" style="margin-top:20px">Future candidates · opportunities, not working products or promised gains</div>'
                   '<div class="cands">'
                   '<div class="cand"><b>Adaptive expert-read policy</b>Choose fill, prediction depth and read size per layer from live readiness counters.</div>'
                   '<div class="cand"><b>Workload-aware CPU/GPU placement</b>Keep the experts this workload uses most in GPU memory; stream the rest.</div>'
                   '<div class="cand"><b>KV-cache / context memory</b>Manage long-context memory on an 8 GB board as its own CC.</div>'
                   '</div>')
    return dict(diagram=diagram, result=result, closing=closing)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    results = json.loads(Path(sys.argv[2]).read_text())
    for name, html in cards(results).items():
        src = out / f'{name}.html'
        src.write_text(html, encoding='utf-8')
        subprocess.run(['google-chrome', '--headless=new', '--disable-gpu', '--hide-scrollbars',
                        '--window-size=1920,1080', f'--screenshot={out / (name + ".png")}', src.as_uri()],
                       check=True, capture_output=True, timeout=120)
        print(out / f'{name}.png')


if __name__ == '__main__':
    main()
