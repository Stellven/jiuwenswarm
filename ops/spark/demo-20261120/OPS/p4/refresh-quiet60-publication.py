"""Refresh the campaign's presenter copy from the verified native 60 GiB report revision."""
import json
from pathlib import Path

base = Path(__file__).resolve().parents[2]
iteration = 'OPS/iterations/spark-p4-cache60-build-overlap'
revision = json.loads((base/iteration/'iteration-v3.json').read_bytes())
cells = sorted(revision['analysis']['focused_comparison']['rows'], key=lambda c: c['prompt_tokens'])
assert revision['report']['status'] == 'verified-p4' and [c['n'] for c in cells] == [10, 10]
heads = json.loads((base/'OPS/final-headlines.json').read_bytes())
row = next(r for r in heads['rows'] if r['id'] == 'c3-60')
assert row['sources'][0]['sha256'] == revision['report']['sha256']
ref = f'[Verified quiet report-v3]({iteration}/report-v3.md)'
screen = f'[Earlier screening report]({iteration}/report-v2.md)'
cap = 'OPS/runs/p4-cache60-aplus-pass-2-quiet-01/result.json'
amendment = 'OPS/p4/cache-abba-60g-quiet-control-amendment.json'
def interval(effect):
    low, high = effect['observed_range']
    return f"{effect['estimate']:+.2f} [{low:+.2f}, {high:+.2f}]"

lines = [
    '## Same-budget result at 60 GiB', '',
    revision['report']['summary'] + ' Each arm ran two fresh launches with the same 60 GiB bank, serving flags, and source conditioning. Greedy output and reasoning hashes matched at both lengths. The closing A+ launch prospectively replaced the entire build-overlapped control. The orchestrator disclosed an idle-priority file pull during the replacement. Its contribution to storage latency was not measured separately. ' + ref + f' · [Frozen order](OPS/p4/cache-abba-60g.json) · [C3 retry amendment](OPS/p4/cache-abba-60g-amendment.json) · [Stock control amendment]({amendment}) · [Closing cap receipt]({cap})', '',
    '| Prompt | Stock A+ median TTFT | C3 median TTFT | Paired seconds saved, median [range] | Paired decode gain, tok/s [range] |',
    '|---:|---:|---:|---:|---:|'
]
for c in cells:
    lines.append(f"| {c['prompt_tokens']} | {c['control']['ttft_s']:.2f} s | {c['candidate']['ttft_s']:.2f} s | {interval(c['paired_ttft_seconds_saved_vs_Aplus'])} | {interval(c['paired_decode_tps_gained_vs_Aplus'])} |")
io = revision['analysis']['paired_first_token_io_saved']
reads = ' and '.join(f"{io[str(c['prompt_tokens'])]['read_bytes']/1e9:.2f} GB" for c in cells)
faults = ' and '.join(f"{io[str(c['prompt_tokens'])]['major_faults']:,.0f}" for c in cells)
lines += ['', f'At 512 and 2048 tokens, the paired median reduction in engine reads before the first token was {reads}, with {faults} fewer major faults. The ranges above span the ten paired requests, drawn from two launches per arm. The idle-priority transfer and elapsed time between launches limit generalization. Stock A+30 still returned the first token sooner in absolute terms on these prompts. ' + ref, '',
          'The earlier report preserves the four original screening windows and their process-I/O and page-residency breakdown. ' + screen, '']
p = base/'report.md'
t = p.read_text()
start,end = t.index('## Same-budget result at 60 GiB'), t.index('## Candidate screening against pooled A+30')
t = t[:start] + '\n'.join(lines) + '\n' + t[end:]
a = t.index('| [C3 seeded cache · 60 GiB]')
b = t.index('\n', a)
t = t[:a] + f"| [{row['arm']}]({iteration}/report-v3.md) | {row['grade']} | {row['ttft']} | {row['decode']} | {row['summary']} |" + t[b:]
t = t.replace('That confirmation remains future work.', 'The closing stock control has now completed under the amended quiet protocol. ' + ref).replace('The last GPU run used the pristine stock binary and the exact C5 serving profile', 'The flags-matched C5 control used the pristine stock binary and the exact C5 serving profile')
p.write_text(t)
p = base/'OPS/DEMO-SCRIPT.md'
text = p.read_text()
start = text.index('Say “', text.index('5. **Measurements.**')) + len('Say “')
end = text.index('At 30 GiB the predictor', start)
text = text[:start] + revision['report']['summary'] + ' The full mirror used the quiet replacement control. Median paired decode changes were ' + row['decode'].replace('tok/s gained','tokens per second') + '. The orchestrator disclosed an idle-priority file transfer. ' + text[end:]
p.write_text(text)
