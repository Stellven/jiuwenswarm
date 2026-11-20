#!/usr/bin/env python3
"""Summarize retained requests; preliminary batches are explicitly descriptive."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--root',type=Path,action='append',required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--label',default='P1 exploratory engine batches; final cross-arm ABBA pending')
a=p.parse_args()
rows=[];excluded=[]
for root in a.root:
 for path in sorted(root.rglob('result.json')):
  result=json.loads(path.read_text())
  if 'ttft_s' not in result:continue
  reasons=[]
  if result.get('discard'):reasons.append('discarded warmup/preliminary request')
  if not result.get('ok') or result.get('ttft_s') is None:reasons.append('request failed')
  if result.get('usage',{}).get('prompt_tokens')!=result.get('prompt_tokens'):reasons.append('actual token count differs')
  if result.get('timings',{}).get('cache_n',0):reasons.append('prompt cache reuse')
  record={**result,'artifact':str(path.resolve()),'artifact_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
  if reasons:excluded.append({**record,'exclusions':reasons})
  else:rows.append(record)
summary=[]
for arm,n in sorted({(r['arm'],r['prompt_tokens']) for r in rows}):
 group=[r for r in rows if r['arm']==arm and r['prompt_tokens']==n]
 ttfts=[r['ttft_s'] for r in group]
 decode=[r['decode_tps'] for r in group if r.get('decode_tps') is not None]
 summary.append({'arm':arm,'prompt_tokens':n,'n':len(group),'ttft_s':statistics.median(ttfts),'ttft_min_s':min(ttfts),'ttft_max_s':max(ttfts),'decode_tps':statistics.median(decode) if decode else None,'greedy_output_hash_count':len({r['output_sha256'] for r in group}),'artifacts':[{'path':r['artifact'],'sha256':r['artifact_sha256']} for r in group]})
for cell in summary:
 controls={r['arm']:r for r in summary if r['prompt_tokens']==cell['prompt_tokens']}
 stock=controls.get('A');strata=controls.get('S');cache=controls.get('A+')
 if stock:
  cell['inverse_ttft_vs_A']=stock['ttft_s']/cell['ttft_s']
 if cache:
  cell['inverse_ttft_vs_Aplus']=cache['ttft_s']/cell['ttft_s']
 if stock and strata:
  denominator=stock['ttft_s']-strata['ttft_s']
  cell['gap_to_strata_closed']=(stock['ttft_s']-cell['ttft_s'])/denominator if denominator>0 else None
  cell['gap_note']='descriptive; warming/order confounded' if denominator>0 else 'A already matches/beats S; positive gap-closure metric undefined'
report={'label':a.label,'aggregate':'median client TTFT; full observed range retained','summary':summary,'eligible_requests':rows,'excluded_requests':excluded}
a.out.parent.mkdir(parents=True,exist_ok=True)
a.out.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
lines=[a.label,'','Median client TTFT; observed ranges are not confidence intervals.','', '| Arm | Prompt tokens | n | TTFT s | Range s | Decode tok/s | Output hashes |','|---|---:|---:|---:|---:|---:|---:|']
for r in summary:
 decode='—' if r['decode_tps'] is None else f'{r["decode_tps"]:.2f}'
 lines.append(f'| {r["arm"]} | {r["prompt_tokens"]} | {r["n"]} | {r["ttft_s"]:.3f} | {r["ttft_min_s"]:.3f}–{r["ttft_max_s"]:.3f} | {decode} | {r["greedy_output_hash_count"]} |')
lines+=['',f'{len(excluded)} requests excluded; reasons and every contributing result digest are in the adjacent JSON.','']
a.out.with_suffix('.md').write_text('\n'.join(lines))
print('\n'.join(lines))
