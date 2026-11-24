"""Cross-check the final candidate screens against their cap receipts, ledger and source artifacts."""
import hashlib
import json
from pathlib import Path

root = Path.home()/'predemo-spark'
def load(path):
    return json.loads(path.read_bytes())
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
heads = load(root/'OPS/final-headlines.json')
for row in heads['rows']:
    assert row['grade'] != 'Awaiting screening' and row['sources']
    for ref in row['sources']:
        assert sha(root/ref['path']) == ref['sha256']
ledger = [json.loads(line) for line in (root/'OPS/LEDGER.jsonl').read_text().splitlines()]
screens = []
for arm in ('c4', 'd', 'c2', 'c5', 'c5-matched-stock'):
    name = f'pooled30-{arm}-01'
    scope = root/'OPS/runs'/name
    cap = load(scope/'result.json')
    assert cap['returncode'] == 0 and cap['reason'] is None and cap['scope_verified']
    assert cap['min_mem_available_bytes'] >= 8*(2**30)
    assert all(int(cap['memory_events'][k]) == 0 for k in ('oom', 'oom_kill', 'oom_group_kill'))
    assert 'Result=oom-kill' not in cap['systemd_properties']
    cap_ledger = [r for r in ledger if r.get('result_path') == str(scope)]
    assert [r['event'] for r in cap_ledger] == ['start','stop']
    window = load(scope/'p4-window/window.json')
    assert window['status']=='complete' and len(window['requests'])==12
    for req in window['requests']:
        f = scope/'p4-window'/req['result']
        assert sha(f)==req['sha256'] and req['status']=='complete'
        log = [r for r in ledger if r.get('result_path')==str(f.parent)]
        assert [r['event'] for r in log]==['request-start','request-stop']
        disk = load(f)
        assert all(log[-1][k]==disk[k] for k in ('ttft_s','decode_tps','reasoning_sha256','output_sha256'))
    sidecar = arm=='c5-matched-stock'
    exp = root/'OPS/iterations'/('spark-pooled30-c5-01' if sidecar else 'spark-'+name)
    if sidecar:
        env=load(exp/'iteration-v2.json')
        assert sha(exp/'report-v2.md')==env['report']['sha256']
        result=env['analysis']['matched_stock_comparison']
        parity=[r['greedy_parity'] for r in result['rows']]
    else:
        env = load(exp/'iteration.json')
        assert sha(exp/'report.md')==env['report']['sha256']
        assert sha(exp/'analysis.json')==env['analysis']['result_artifact']['sha256']
        result = env['analysis']['pooled_comparison']
        assert result['matched_ordinals']==[3,4,5,6] and result['control_count']==4
        parity=result['greedy_parity']
    assert sorted((r['prompt_tokens'],r['n']) for r in result['rows'])==[(512,4),(2048,4)]
    screens.append(dict(arm=cap['arm'],scope=name,start=cap['start'],stop=cap['stop'],scope_sha256=sha(scope/'result.json'),
                        request_starts=12,request_stops=12,min_mem_available_gib=cap['min_mem_available_bytes']/2**30,
                        memory_events=cap['memory_events'],report_sha256=env['report']['sha256'],greedy_parity=parity))
print(json.dumps(dict(schema='spark-final-campaign-verification/1',headline_source_sha256=sha(root/'OPS/final-headlines.json'),
                      headline_rows=len(heads['rows']),pooled_screens=screens),indent=2))
