"""Phase 0: compare warm AQB expert placement settings with one resident server at a time."""
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from jiuwenswarm.factory import capped_run
from scripts.factory import lab_v4_fast as lab, lab_v4_quiet as quiet, r8_bench_cells as cells
from scripts.factory import r8_final_benchmark as bench
from scripts.factory.r8_derive_p_ttft import derive

OUT = bench.BASE / 'lab/r9-placement-check'


def status(doing, resident, next_step, blocked=None):
    lab.save(bench.BRIDGE/'STATUS.json', dict(ts=datetime.now().astimezone().isoformat(timespec='seconds'),
        phase='R2 Phase 0', doing=doing, model_loaded=resident, next=next_step, blocked_on=blocked))


def measure_share(proposal, identity, prior, binary, prompt, share):
    prefix = 'share-' + str(share)
    receipt = OUT / (prefix + '.json')
    if receipt.exists():
        raise RuntimeError(f'Check existing receipt before resuming: {receipt}')
    leg = prior['load']
    scope = capped_run.RunScope(OUT, OUT, dict(resources=dict(memory_cap=capped_run.CAP, device_budget_mib=110000,
        floor_gib=8, gate_wait_s=0)), uuid4().hex, prefix + '.progress.log')
    args = list(proposal['base_args'])
    args[args.index('--moe-cache-cpu-share')+1] = str(share)
    args += ['-c',str(leg['ctx']),'-np',str(leg['np']),'-b',str(leg['batch']),'-ub',str(leg['ubatch']),
             '--moe-cache-mib',str(leg['moe_cache_mib'])]
    row = dict(share=share, identity=identity, pack=prior['pack'], status='admitting', cache_prompt=False,
               request='p512', state='warm', n_predict=32, memory_cap=scope.cap, device_budget_mib=110000)
    server = None
    with quiet.Monitor(quiet.policy(quiet.EMPTY), slots=1, stop_on_gate=True) as mon:
        try:
            status(f'Admitting CPU share {share}', False, 'Prime the resident engine and measure warm p512')
            mon.wait('pre_launch','loading',lab.log)
            row['gate'] = scope.gate()
            row['status'] = 'launch_reserved'
            lab.save(receipt,row)
            server = capped_run.Server(scope,str(binary),prior['pack']['first_shard'],args,
                                       capped_run.user_bus_env(),prefix+'.server.log')
            mon.server = server
            mon.mark('ready','between_rows')
            row.update(pid=server.proc.pid, argv=server.argv, observed=bench.validate_ready(server,leg), ready_s=server.ready_s)
            status(f'Priming CPU share {share}',True,'Time one warm p512 request')
            n = cells.tokenize(server,proposal,{'p512':prompt})['p512']
            mon.wait('start','during',lab.log)
            prime = lab.request(server,prompt,32,benchmark=True)
            mon.mark('end','between_rows')
            if prime['generated_tokens'] != 32 or prime['prompt_tokens'] != n:
                raise ValueError('Priming completion differs from benchmark')
            row['prime'] = dict(generated_tokens=32,prompt_tokens=n)
            status(f'Measuring warm p512 at CPU share {share}',True,'Close server and check warm result')
            measured, evidence, error = lab.measure(server,prompt,32,n,mon,benchmark=True)
            row.update(measured,quiet=evidence, repeat=1, arm='AQB' if share == 0 else 'AQBC')
            if error:
                raise error
            row['derived_ttft_ms'] = derive(row)['derived_ttft_ms']
            row['status']='complete'
        except BaseException as exc:
            row.update(status='stopped',error=str(exc))
            raise
        finally:
            if server:
                server.close()
                mon.server=None
            mon.mark('arm_end')
            row['ended_utc']=bench.now()
            lab.save(receipt,row)
            lab.save(OUT/(prefix+'.admission.json'),[s for s in mon.samples if s['phase'] not in ('during','end')])
            status(f'Closed CPU share {share}',False,'Check receipts and next setting')
    return row


def main():
    proposal, identity, _ = bench.check_inputs()
    prior = bench.read(bench.OUT/'3.load.json')
    binary = next(Path(arg) for arg in prior['argv'] if arg.endswith('/llama-server'))
    if prior['factory_provenance'] != identity or bench.digest(binary) != identity['llama_server_sha256']:
        raise ValueError('AQB identity mismatch')
    prompt=cells.read_prompts(proposal)['p512']
    for share in (0,0.25,0.5):
        row=measure_share(proposal,identity,prior,binary,prompt,share)
        print(share,row['quiet']['status'],row['derived_ttft_ms'],row['decode_tokens_per_second'],row['request_total_ms'],flush=True)
    status('All three settings closed',False,'Compare accepted results against AQB')


if __name__ == '__main__':
    main()
