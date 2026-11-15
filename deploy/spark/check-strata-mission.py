"""Read-only independent check of retained contract-bound Strata lab cells."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jiuwenswarm.factory.engine_adapters import parse_protocol, verify_cell_evidence


def summarize_results(task_id, results):
    """Require the same experiment identity before accepting repeatability."""
    complete=[r for r in results if r['status']=='verified_complete']
    identities={v['canonical_sha256'] for r in complete for v in r['requests']}
    groups={r.get('comparison_group') for r in complete}
    comparable=bool(complete) and None not in groups and len(groups)==1
    phases={}
    for i,name in enumerate(['first_after_initialization','repeat']):
        rates=[r['requests'][i]['decode_tps'] for r in complete if len(r['requests'])>i]
        if rates:phases[name]=dict(cells=len(rates),minimum=min(rates),median=statistics.median(rates),maximum=max(rates),unit='decode_tokens_per_second')
    report=dict(task_id=task_id,successful_cells=len(complete),failed_cells=len(results)-len(complete),
        generated_tokens=sum(v['generated_tokens'] for r in complete for v in r['requests']),
        phases=phases,within_process_repeats_equal=bool(complete) and all(r['repeat_equal'] for r in complete),
        fresh_process_output_identities=len(identities),configurations_comparable=comparable,
        deterministic_reference_accepted=comparable and len(identities)==1 and len(complete)>=3,
        semantic_accuracy='not_evaluated',performance_improvement='not_established',
        cache_protocol='First request after engine initialization and repeat; no cold-SSD claim.',results=results)
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--home',type=Path,required=True);p.add_argument('--task',required=True)
    p.add_argument('--output',type=Path);a=p.parse_args();results=[]
    with sqlite3.connect('file:'+str(a.home/'factory.sqlite')+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute("SELECT * FROM attempts WHERE task_id=? AND kind='lab' ORDER BY rowid",(a.task,)).fetchall()
    for row in rows:
        request=json.loads(row['request'])
        if request.get('adapter')!='strata-v1':continue
        root=a.home/'lab-spool'/row['attempt_id'];worker=json.loads((root/'worker.json').read_text())
        if worker['execution_outcome']!='ok':
            results.append(dict(attempt_id=row['attempt_id'],status='failed_retained',error=worker.get('error'),
                collector_reason=worker.get('collector',{}).get('reason')))
            continue
        manifest=json.loads((root/'manifest.json').read_text());content={}
        for name,want in manifest['files'].items():
            path=(root/name).resolve()
            if not path.is_relative_to(root.resolve()):raise ValueError('Manifest escapes spool')
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=want:raise ValueError('Changed artifact: '+name)
            content[name]=data
        if json.loads(content['config.json'])!=dict(request,lab_run_id=row['attempt_id']):raise ValueError('Configuration identity differs')
        verify_cell_evidence(content,request)
        native=parse_protocol(content['cell/stdout.log'].decode(),content['cell/stderr.log'].decode(),request['contract'])
        if native['requests']!=worker['requests']:raise ValueError('Raw metrics differ from worker record')
        final=json.loads(content['cell/report.json'])
        if not (final['reason']=='completed' and final['container_removed'] and final['quiescent'] and final['container_exit_code']==0):
            raise ValueError('Final execution or cleanup invalid')
        samples=[json.loads(line) for line in content['cell/samples.jsonl'].splitlines()]
        results.append(dict(attempt_id=row['attempt_id'],status='verified_complete',requests=native['requests'],
            comparison_group=worker['comparison_group'],repeat_equal=native['repeat_equal'],
            min_host_available_bytes=min(v['available_bytes'] for v in samples),
            max_sampled_cgroup_bytes=max(v.get('cgroup_current') or 0 for v in samples),
            container_removed=final['container_removed'],image=request['admission']['image']['id']))
    report=summarize_results(a.task,results)
    if a.output:
        with a.output.open('x') as stream:json.dump(report,stream,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k!='results'}))

if __name__=='__main__':main()
