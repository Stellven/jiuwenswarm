"""Bounded benchmark-only RSI for a pinned pure function; no product activation."""
from __future__ import annotations
import argparse, asyncio, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

IMAGE = 'sha256:00026931a8e236d255efca8d2e90ea49ae04989539fca4d418d318a98fa93ab2'
DOCKER = ['/opt/ai4r-rsi-host/payload/usr/bin/docker','-H','unix:///run/ai4r-rsi-docker/docker.sock']
KERNEL = Path('/opt/ai4r-rsi-frozen-v18-03ed3199/jiuwenswarm/research')
def sha(raw): return hashlib.sha256(raw).hexdigest()
def encoded(v): return (json.dumps(v,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
def write_new(path,v):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:
        f.write(v if isinstance(v,bytes) else encoded(v)); f.flush();os.fsync(f.fileno())
def checked(path,pin):
    raw=Path(path).read_bytes()
    if sha(raw)!=pin: raise ValueError('PINNED_BYTES_DIFFER')
    return raw

class Campaign:
    def __init__(self, manifest, source_root):
        self.path=Path(manifest).resolve(); self.raw=self.path.read_bytes();self.digest=sha(self.raw)
        self.m=json.loads(self.raw);self.root=Path(self.m['run_root'])
        self.source=Path(source_root).resolve();self.native=self.source.parent
        self.parent=Path(self.m['parent']['path'])
        checked(self.parent,self.m['parent']['sha256'])
        self.code=self.source/'benchmarks/ccbench/rsi'
    def report_path(self,mode,i,body):
        return self.root/'reports'/f'{mode}-{i}-{sha(Path(body).read_bytes())}.json'
    def execute(self,mode,i,body):
        report=self.report_path(mode,i,body)
        if report.exists(): raise ValueError('CONSUMED_STAGE_NO_REPLAY')
        ident=f"{self.m['run_id']}-{mode}-{i}"
        control=self.root/'containers'/ident;control.mkdir(parents=True,exist_ok=False)
        argv=['create','--name','ai4r-function-'+ident,'--init','--read-only','--network','none',
              '--user','0:0','--cap-drop','ALL']
        for cap in ['SETUID','SETGID','CHOWN','FOWNER','DAC_OVERRIDE','KILL']:argv+=['--cap-add',cap]
        argv+=['--security-opt','no-new-privileges:true','--security-opt',
          'seccomp=/opt/ai4r-rsi-development-admin-20261026/executor.json','--cgroupns','host',
          '--memory','512m','--memory-swap','512m','--pids-limit','64','--cpus','2',
          '--tmpfs','/tmp:rw,nosuid,nodev,size=64m','--entrypoint','/opt/venv/bin/python']
        for p,ro in [(self.source,True),(self.native/'input',True),(self.root,False),
                     (Path(self.m['cgroup_root']),False),
                     (KERNEL/'executor.py',True),(KERNEL/'_executor_probe.py',True)]:
            argv+=['--mount',f'type=bind,src={p},dst={p}'+(',readonly' if ro else '')]
        argv += [IMAGE,'-I','-B',str(self.code/'function_executor.py'),
                 '--manifest',str(self.path),'--manifest-sha256',self.digest,
                 '--mode',mode,'--iteration',str(i),'--candidate',str(body),
                 '--candidate-sha256',sha(Path(body).read_bytes())]
        write_new(control/'claim.json',{'argv':DOCKER+argv,'image':IMAGE,'manifest_sha256':self.digest})
        def docker(args,timeout=60):return subprocess.run(DOCKER+args,capture_output=True,check=True,timeout=timeout)
        cid=docker(argv).stdout.decode().strip()
        write_new(control/'container.json',{'cid':cid})
        docker(['start',cid]); deadline=time.monotonic()+2400
        while True:
            info=json.loads(docker(['inspect',cid]).stdout)[0]
            if not info['State']['Running']:break
            if time.monotonic()>deadline:raise RuntimeError('STAGE_DEADLINE_UNKNOWN_EFFECT_NO_REPLAY')
            time.sleep(1)
        logs=docker(['logs',cid]).stdout
        write_new(control/'stdout.log',logs)
        write_new(control/'exit.json',{'cid':cid,'state':info['State'],'logs_sha256':sha(logs)})
        if info['State']['Pid']!=0 or info['State']['ExitCode']!=0:
            raise RuntimeError('PROTECTED_STAGE_FAILED: '+logs.decode(errors='replace')[-1800:])
        result=json.loads(report.read_bytes())
        print(json.dumps({'mode':mode,'iteration':i,'status':result['status'],
                          'passed':result.get('passed'),'statistics':result.get('statistics')}),flush=True)
        return result
    def existing(self,mode,i,body):
        p=self.report_path(mode,i,body)
        if not p.is_file():raise ValueError('REQUIRED_COMPLETED_STAGE_MISSING')
        r=json.loads(p.read_bytes())
        if r['manifest_sha256']!=self.digest or r['candidate_sha256']!=sha(Path(body).read_bytes()):
            raise ValueError('COMPLETED_STAGE_PIN_DIFFERS')
        return r
    def baseline(self):
        write_new(self.root/'baseline-started.json',{'manifest_sha256':self.digest,'model_calls':0})
        parent=self.execute('evaluate',0,self.parent)
        if not parent['passed']:raise ValueError('HISTORICAL_CC_PARENT_FAILED_EXISTING_CHECKS')
        self.execute('calibrate',0,self.parent)
        base=self.execute('benchmark',0,self.parent)
        write_new(self.root/'baseline-complete.json',{'manifest_sha256':self.digest,'report':str(self.report_path('benchmark',0,self.parent)),'model_calls':0})
        return base
    async def run(self):
        from function_model import propose
        base=self.existing('benchmark',0,self.parent)
        if not base.get('self_comparison'):raise ValueError('PARENT_AA_REQUIRED')
        write_new(self.root/'loop-started.json',{'manifest_sha256':self.digest,
            'max_iterations':5,'max_model_calls':10,'max_no_progress':3,
            'source_pins':{p.name:sha(p.read_bytes()) for p in self.code.glob('function_*.py')}})
        spec=json.loads((self.native/'input/public-spec.json').read_bytes())
        best={'iteration':0,'body_path':str(self.parent),'body_sha256':self.m['parent']['sha256'],'median_ratio':1.0}
        history=[];stall=0;stop='max_iterations';error=None
        try:
            for iteration in range(1,6):
                current=Path(best['body_path']).read_text()
                visible=[{'iteration':h['iteration'],'kept':h.get('kept',False),
                          'correctness':h.get('correctness'),'timing':h.get('timing'),
                          'reason':h.get('reason')} for h in history]
                context={'spec':spec['spec'],'examples':spec.get('examples',[]),
                         'current_best_source':current,'original_parent_source':self.parent.read_text(),
                         'history':visible,'objective':'Preserve behavior, reduce protected batched execution wall time.',
                         'constraints':['Change only the function implementation and pure helpers.',
                            'No file/process/network/clock access, introspection, or fixture-specific branches.',
                            'Only standard-library re and math imports are allowed. No dunder attributes.',
                            'The frozen checker forbids re.compile; use re.fullmatch or equivalent public APIs.',
                            'No memoization, cache decorators, mutable defaults or global mutable state.',
                            'Do not alter checks or benchmark. Preserve ValueError behavior and input immutability.'],
                         'selection_gates':{'minimum_parent_gain':0.1,'parent_ratio_ci_upper_max':0.9,
                                            'max_workload_regression':0.05,'must_beat_current_best_above_noise':True}}
                diagnosis=await propose(self.root,
                    'Analyze the pure function for general performance improvements. Return a concise diagnosis only. '
                    'Do not assume undisclosed test inputs.\n'+json.dumps(context),
                    phase='diagnosis',iteration=iteration,model='gpt-6.1-sol')
                proposal=await propose(self.root,
                    'Produce the optimized implementation based on this diagnosis and evidence. '
                    'Return exactly one Python code block, defining '+self.m['function']+
                    ' with the same signature. No benchmarks or tests.\n'+json.dumps(context)+
                    '\nDiagnosis:\n'+diagnosis['text'],
                    phase='proposal',iteration=iteration,model='gpt-6.1-sol')
                blocks=re.findall(r'```(?:python|py)?\s*\n(.*?)```',proposal['text'],re.S)
                row={'iteration':iteration,'diagnosis_receipt':diagnosis['receipt_ref'],
                     'proposal_receipt':proposal['receipt_ref'],'kept':False}
                if len(blocks)!=1:
                    row['reason']='invalid_code_response';stall+=1
                else:
                    raw=(blocks[0].strip()+'\n').encode()
                    body=self.root/'candidates'/f'iteration-{iteration}.py';write_new(body,raw)
                    row.update(candidate_path=str(body),candidate_sha256=sha(raw))
                    quality=self.execute('evaluate',iteration,body)
                    row['correctness']={'passed':quality['passed'],'passed_count':quality.get('passed_count'),
                         'case_count':quality.get('case_count'),'gate_failures':quality.get('gate_failures',[]),
                         'held_out_failure_count':len(quality.get('held_out_failing_ids',[]))}
                    if quality['passed']:
                        measured=self.execute('benchmark',iteration,body)
                        if not measured.get('passed') or 'statistics' not in measured:
                            row['reason']=measured.get('reason','benchmark_rejected');stall+=1
                        else:
                            stats=measured['statistics']
                            row['timing']={k:stats[k] for k in ['median_ratio','relative_gain','ratio_confidence_interval','objective_met','rows']}
                            if stats['objective_met'] and stats['ratio_confidence_interval'][1]<best['median_ratio']:
                                best={'iteration':iteration,'body_path':str(body),'body_sha256':sha(raw),
                                      'median_ratio':stats['median_ratio'],'benchmark_report':str(self.report_path('benchmark',iteration,body))}
                                row['kept']=True;row['reason']='qualified_improvement';stall=0
                            else:row['reason']='did_not_beat_best';stall+=1
                    else:row['reason']=quality.get('reason','correctness_failed');stall+=1
                history.append(row);write_new(self.root/'iterations'/f'{iteration}.json',row)
                print(json.dumps({'iteration':iteration,'kept':row['kept'],'reason':row['reason'],'best':best}),flush=True)
                if stall>=3:stop='no_progress';break
        except Exception as exc:
            stop='error';error={'type':type(exc).__name__,'message':str(exc)}
        selected=checked(best['body_path'],best['body_sha256'])
        write_new(self.root/'selected-body.py',selected)
        result={'schema':'ai4r-pure-function-rsi-result:1','run_id':self.m['run_id'],
                'scope':'benchmark_only_no_product_activation','manifest_sha256':self.digest,
                'stop_reason':stop,'error':error,'selection':best,'iterations':history,
                'historical_parent_sha256':self.m['parent']['sha256'],
                'completed_iterations':len(history),'parent_baseline':str(self.report_path('benchmark',0,self.parent)),
                'claim':'Protected batched execution wall time; not model generation or whole-agent latency.'}
        write_new(self.root/'result.json',result);print(json.dumps(result),flush=True)
        if error:raise RuntimeError('LOOP_STOPPED_WITH_RETAINED_RESULT: '+error['message'])
        return result

def main():
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['baseline','run'])
    p.add_argument('--manifest',required=True);p.add_argument('--source-root',required=True)
    a=p.parse_args();c=Campaign(a.manifest,a.source_root)
    if a.operation=='baseline':c.baseline()
    else:asyncio.run(c.run())
if __name__=='__main__':main()
