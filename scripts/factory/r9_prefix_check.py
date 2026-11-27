"""One capped p2048 prefix-store trial, reusing the delivered AQB server and request clock."""
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from jiuwenswarm.factory import capped_run
from scripts.factory import lab_v4_fast as lab, lab_v4_quiet as quiet, r8_bench_cells as cells
from scripts.factory import r8_final_benchmark as bench

OUT = bench.BASE/'lab/r9-aqbc/phase-0b'
FLAGS = ['--swa-full','--ctx-checkpoints','32']
QUESTIONS = (
    'Which two words finish the field notebook above? Read the last line carefully, preserve their original order, and answer in one short sentence using only information from the document.',
    'Name three words that appear just before the end of this field notebook. Quote them in the order they appear and give a brief answer using only the supplied document.',
)


def status(doing, loaded, next_step, blocked=None):
    lab.save(bench.BRIDGE/'STATUS.json',dict(ts=datetime.now().astimezone().isoformat(timespec='seconds'),
        phase='R2 Phase 0b',doing=doing,model_loaded=loaded,next=next_step,blocked_on=blocked))


def questions(document):
    end='<|eot|><|start|>assistant'
    if not document.endswith(end):
        raise ValueError('Unexpected benchmark rendering')
    return [document[:-len(end)]+'\n\n'+q+end for q in QUESTIONS]


def run_request(server, monitor, prompt, *, cache_prompt):
    ids=server.post(dict(content=prompt,add_special=True,parse_special=True),path='/tokenize')['tokens']
    log_offset=server.log.stat().st_size
    first,_=monitor.wait('start','during',lab.log)
    metrics=lab.request(server,prompt,32,benchmark=True,cache_prompt=cache_prompt)
    last=monitor.mark('end','between_rows')
    samples=monitor.samples[first:last+1]
    with server.log.open('rb') as stream:
        stream.seek(log_offset)
        lines=stream.read().decode(errors='replace').splitlines()
    evidence=[line for line in lines if 'cached n_tokens =' in line or 'restored context checkpoint' in line]
    cached=[int(m.group(1)) for line in evidence if (m:=re.search(r'cached n_tokens = (\d+)',line))]
    if metrics['generated_tokens']!=32 or metrics['client_ttft_ms'] is None:
        raise ValueError('Incomplete completion')
    reasons=quiet.evidence_issues(samples,monitor.limits)
    anchor=next(e['elapsed_ms'] for e in metrics['stream_arrivals'] if e['progress'])
    return dict(metrics,tokenized_prompt_tokens=len(ids),cache_prompt=cache_prompt,question=prompt,
                derived_ttft_ms=round(anchor+metrics['prompt_ms']-metrics['prompt_progress'][0]['time_ms'],1),
                cached_tokens=cached[0] if cached else None,server_log_evidence=evidence,
                quiet=dict(status='excluded' if reasons else 'accepted',reasons=reasons,samples=samples))


def main():
    out=OUT/'check.json'
    if out.exists():
        raise RuntimeError('Phase 0b already has a receipt')
    p,identity,_=bench.check_inputs()
    prior=bench.read(bench.OUT/'3.load.json')
    binary=next(Path(a) for a in prior['argv'] if a.endswith('/llama-server'))
    if prior['factory_provenance']!=identity or bench.digest(binary)!=identity['llama_server_sha256']:
        raise ValueError('AQB identity mismatch')
    leg=prior['load']
    args=[*p['base_args'],'-c',str(leg['ctx']),'-np','1','-b',str(leg['batch']),'-ub',str(leg['ubatch']),
          '--moe-cache-mib',str(leg['moe_cache_mib']),*FLAGS]
    scope=capped_run.RunScope(OUT,OUT,dict(resources=dict(memory_cap=capped_run.CAP,device_budget_mib=110000,
        floor_gib=8,gate_wait_s=0)),uuid4().hex,'progress.log')
    report=dict(status='admitting',identity=identity,pack=prior['pack'],rows=[],document=p['speed_prompt_pins']['p2048'],
                memory_cap=scope.cap,device_budget_mib=110000)
    prompts=questions(cells.read_prompts(p)['p2048'])
    server=None
    with quiet.Monitor(quiet.policy(quiet.EMPTY),slots=1,stop_on_gate=True) as monitor:
        try:
            monitor.wait('pre_launch','loading',lab.log)
            report['gate']=scope.gate()
            report['status']='launch_reserved'
            lab.save(out,report)
            server=capped_run.Server(scope,str(binary),prior['pack']['first_shard'],args,capped_run.user_bus_env(),'server.log')
            monitor.server=server
            monitor.mark('ready','between_rows')
            report.update(status='loaded',argv=server.argv,pid=server.proc.pid,observed=bench.validate_ready(server,leg))
            lab.save(out,report)
            for index,prompt in enumerate(prompts,1):
                status(f'Running 2048 document question {index} of 2',True,'Verify follow-up reuse and first-token latency')
                report['rows'].append(run_request(server,monitor,prompt,cache_prompt=True))
                lab.save(out,report)
            report['status']='complete'
        except BaseException as error:
            report.update(status='stopped',error=str(error))
            raise
        finally:
            if server:
                server.close()
                monitor.server=None
            monitor.mark('arm_end')
            report['ended_utc']=bench.now()
            lab.save(out,report)
            lab.save(OUT/'admission.json',[s for s in monitor.samples if s['phase'] not in ('during','end')])
            status('Server closed; reviewing Phase 0b evidence',False,'Apply the owner’s phase gate')


if __name__=='__main__':
    main()
