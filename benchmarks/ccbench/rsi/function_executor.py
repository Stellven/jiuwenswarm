"""Finite benchmark-only pure-function jobs through the immutable V18 executor.

Manifest schema ai4r-pure-function-benchmark:1 pins parent/cases/checker bytes,
function/case identifiers, run/cgroup roots, worker metadata references, limits,
and timing settings. No product admission or utility-bootstrap authority is used.
Expected results remain in this owner; a worker receives only current arguments.
All generated source runs under the frozen executor and single-process policy.
"""
from __future__ import annotations
import argparse
import ast
import asyncio
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from jiuwenswarm.research_rsi.records import RecordStore, encoded
from jiuwenswarm.research_rsi.process_policy import POLICY, apply_policy
from jiuwenswarm.research_rsi.targets.capsule_executor import (
    load_v18_executor, bounded_executor, ensure_worker_traversal,
    WORKER_UID, WORKER_GID)
from jiuwenswarm.research_rsi.targets.cgroup_lifecycle import check_capacity, retire_owned_group
from jiuwenswarm.research_rsi.targets.capsule_benchmark import compare_paired_samples

class CandidateRejected(Exception):
    pass


SCHEMA = 'ai4r-pure-function-benchmark:1'
REPORT = 'ai4r-pure-function-report:1'
SAFE_MEMBERS = {
    're': {'fullmatch','match','search','finditer','findall','split','sub','subn','escape',
           'ASCII','A','IGNORECASE','I','MULTILINE','M','DOTALL','S','VERBOSE','X','NOFLAG','UNICODE','U','error'},
    'math': {'ceil','floor','trunc','fabs','factorial','fmod','remainder','frexp','ldexp','modf','isclose',
             'isfinite','isinf','isnan','gcd','lcm','comb','perm','prod','fsum','sumprod','exp','exp2','expm1',
             'log','log2','log10','log1p','pow','sqrt','isqrt','cbrt','sin','cos','tan','asin','acos','atan',
             'atan2','hypot','dist','degrees','radians','sinh','cosh','tanh','asinh','acosh','atanh',
             'erf','erfc','gamma','lgamma','copysign','nextafter','ulp','pi','e','tau','inf','nan'},
}
SAFE_IMPORTS = set(SAFE_MEMBERS)
SAFE_ATTRIBUTES = set().union(*SAFE_MEMBERS.values(), {
    # Finite string, regex-match, scalar and local-container operations only.
    'strip','lstrip','rstrip','isdigit','isdecimal','isnumeric','isspace','isalpha','isalnum','isascii',
    'islower','isupper','istitle','lower','upper','casefold','title','capitalize','swapcase','startswith',
    'endswith','find','rfind','index','rindex','count','replace','rsplit','splitlines','partition','rpartition',
    'join','zfill','ljust','rjust','center','removeprefix','removesuffix','translate','maketrans','encode','decode',
    'group','groups','groupdict','span','start','end','lastindex','lastgroup','pattern','flags',
    'append','extend','insert','pop','remove','clear','reverse','sort','copy','get','keys','values','items',
    'setdefault','update','popitem','add','discard','intersection','union','difference','symmetric_difference',
    'issubset','issuperset','isdisjoint','bit_length','bit_count','as_integer_ratio','is_integer',
})
DENIED_NAMES = {'open','eval','exec','compile','getattr','setattr','delattr','globals','locals','vars','dir',
                'input','print','help','breakpoint','exit','quit','memoryview'}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def real(path, directory=False):
    p = Path(path)
    need(p.is_absolute() and not any(q.is_symlink() for q in (p, *p.parents)), 'REAL_ABSOLUTE_PATH_REQUIRED')
    need(p.is_dir() if directory else p.is_file(), 'REQUIRED_PATH_ABSENT')
    return p


def pinned(value):
    need(isinstance(value, dict) and set(value) == {'path','sha256'}, 'EXACT_FILE_PIN_REQUIRED')
    raw = real(value['path']).read_bytes()
    need(sha(raw) == value['sha256'], 'PINNED_BYTES_DIFFER')
    return raw


def exclusive(path, value):
    raw = value if isinstance(value, bytes) else encoded(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def source_check(raw, function, checker):
    """Defense in depth only; V18 confinement is the execution boundary."""
    try:
        code = raw.decode('utf-8')
        if not 0 < len(raw) <= 262144 or checker.BANNED.search(code):
            return 'empty/oversized source or original checker banned expression'
        tree = ast.parse(code)
        if not any(isinstance(n, ast.FunctionDef) and n.name == function for n in tree.body):
            return 'required function absent'
        def immutable(value):
            return value is None or type(value) in (bool,int,float,complex,str,bytes) or (
                type(value) is tuple and all(immutable(item) for item in value))
        def constant(node, names=()):
            if isinstance(node,ast.Name): return node.id in names
            try:return immutable(ast.literal_eval(node))
            except (ValueError,TypeError,SyntaxError):return False
        constants=set()
        for node in tree.body:
            if isinstance(node,(ast.Import,ast.ImportFrom,ast.FunctionDef)):continue
            if isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):continue
            if isinstance(node,(ast.Assign,ast.AnnAssign)):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                if not all(isinstance(t,ast.Name) for t in targets) or not constant(node.value,constants):
                    return 'module bindings must be immutable constants'
                constants.update(t.id for t in targets);continue
            return 'module effects or mutable caches forbidden'
        for node in ast.walk(tree):
            if isinstance(node,(ast.Global,ast.Nonlocal)):
                return 'cross-call mutable state forbidden'
            if isinstance(node,ast.FunctionDef):
                if node.decorator_list: return 'decorators and memoization forbidden'
                if any(not constant(d,constants) for d in [*node.args.defaults,*[d for d in node.args.kw_defaults if d is not None]]):
                    return 'mutable or computed function defaults forbidden'
            if isinstance(node,ast.Attribute) and isinstance(node.ctx,(ast.Store,ast.Del)):
                return 'persistent attribute mutation forbidden'
            if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom)):
                return 'only synchronous pure functions are supported'
            if isinstance(node, ast.Import):
                if any(n.name not in SAFE_IMPORTS for n in node.names): return 'import outside finite pure-function allowlist'
            if isinstance(node, ast.ImportFrom):
                if node.level or node.module not in SAFE_IMPORTS or any(n.name not in SAFE_MEMBERS.get(node.module,set()) for n in node.names):
                    return 'import outside finite pure-function allowlist'
            if isinstance(node, ast.Name) and (node.id in DENIED_NAMES or '__' in node.id):
                return 'introspection or effect-capable name forbidden'
            if isinstance(node, ast.Attribute) and node.attr not in SAFE_ATTRIBUTES:
                return 'attribute outside finite public pure-function allowlist'
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and '__' in node.value:
                return 'dunder introspection string forbidden'
        return None
    except (UnicodeError, SyntaxError, ValueError) as e:
        return type(e).__name__


def operator_policy_checks(parent, function, checker):
    """AST-only checks: never execute candidate or parent function bodies."""
    need(source_check(parent,function,checker) is None, 'PARENT_SOURCE_POLICY_REJECTED')
    examples = [
        (True, "import re\ndef probe(s):\n return re.fullmatch(r'[0-9]+', s) is not None\n"),
        (False, "import re\ndef probe(s):\n return re.sys.stdout\n"),
        (False, "from re import sys\ndef probe(s):\n return sys.stdout\n"),
        (False, "def probe(s, cache={}):\n return cache.setdefault(s, 1)\n"),
        (False, "import functools\n@functools.lru_cache()\ndef probe(s):\n return 1\n"),
        (False, "import re\ndef probe(s):\n return re.compile(s)\n"),
    ]
    for accepted, source in examples:
        need((source_check(source.encode(),'probe',checker) is None) == accepted, 'OPERATOR_POLICY_CHECK_FAILED')


def program(function, iterations):
    # The clock is external. A candidate cannot report an invented elapsed time.
    body = ("import json,runpy,sys\n"
            "args=json.load(open('/resources/input.json'))\n"
            "before=json.dumps(args,sort_keys=True,separators=(',',':'),allow_nan=False)\n"
            "namespace=runpy.run_path('/resources/body.py')\n"
            f"fn=namespace[{function!r}]\n"
            "try:\n"
            f" for _ in range({iterations}):\n  result=fn(*args)\n"
            " row={'got':json.loads(json.dumps(result,allow_nan=False))}\n"
            "except BaseException as error:\n row={'error':type(error).__name__}\n"
            "row['input_unmodified']=before==json.dumps(args,sort_keys=True,separators=(',',':'),allow_nan=False)\n"
            "sys.stdout.write(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False))\n").encode()
    return apply_policy(body, POLICY)


def load_manifest(path, digest):
    raw = real(path).read_bytes(); need(sha(raw) == digest, 'MANIFEST_PIN_DIFFERS')
    m = json.loads(raw)
    fields = {'schema','run_id','run_root','cgroup_root','parent','cases','checker','case_id','function','worker','limits','timing'}
    need(set(m) == fields and m['schema'] == SCHEMA, 'CLOSED_MANIFEST_REQUIRED')
    need(re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}', m['run_id']) is not None, 'BOUNDED_RUN_ID_REQUIRED')
    need(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', m['function']) is not None, 'FINITE_FUNCTION_NAME_REQUIRED')
    lim = m['limits']; timing = m['timing']
    need(set(lim) == {'max_jobs','timeout_s','memory_mb','pids_max'}
         and type(lim['max_jobs']) is int and 1 <= lim['max_jobs'] <= 3000
         and lim['timeout_s'] == 20 and lim['memory_mb'] == 256 and lim['pids_max'] == 16, 'FIXED_EXECUTION_LIMITS_REQUIRED')
    need(set(timing) == {'repetitions','warmups','min_batch','max_batch','target_s'}
         and timing['repetitions'] == 11 and timing['warmups'] == 2
         and type(timing['min_batch']) is int and type(timing['max_batch']) is int
         and 100000 <= timing['min_batch'] <= timing['max_batch'] <= 2000000
         and type(timing['target_s']) in (int,float) and .5 <= timing['target_s'] <= 1, 'FIXED_TIMING_PROTOCOL_REQUIRED')
    need(set(m['worker']) == {'contract_ref','environment_ref','hardware_ref'}, 'WORKER_METADATA_REQUIRED')
    for pin in m['worker'].values():
        need(isinstance(pin,dict) and set(pin) == {'id','sha256'} and re.fullmatch('[a-f0-9]{64}',pin['sha256']), 'EXACT_METADATA_REF_REQUIRED')
    case_list = json.loads(pinned(m['cases']))
    need(isinstance(case_list,list), 'FROZEN_PARTNER_CASE_LIST_REQUIRED')
    matches = [c for c in case_list if c.get('id') == m['case_id']]
    need(len(matches) == 1 and matches[0]['function'] == m['function'], 'EXACT_CASE_FUNCTION_REQUIRED')
    case = matches[0]
    need(all(isinstance(case[k],list) and case[k] for k in ('gate','score')), 'FROZEN_GATE_SCORE_REQUIRED')
    for test in case['gate'] + case['score']:
        need(isinstance(test,dict) and set(test) in ({'args','expect'},{'args','raises'})
             and isinstance(test['args'],list), 'CLOSED_TEST_RECORD_REQUIRED')
    parent = pinned(m['parent']); checker_raw = pinned(m['checker'])
    spec = importlib.util.spec_from_file_location('frozen_function_checker_' + sha(checker_raw), m['checker']['path'])
    checker = importlib.util.module_from_spec(spec); spec.loader.exec_module(checker)
    need(callable(checker.same) and hasattr(checker.BANNED,'search'), 'ORIGINAL_CHECKER_API_REQUIRED')
    operator_policy_checks(parent,m['function'],checker)
    return m, case, parent, checker


class Executor:
    def __init__(self, manifest, manifest_sha):
        need(os.name == 'posix' and os.geteuid() == 0, 'ROOT_PROTECTED_EXECUTOR_REQUIRED')
        self.m, self.manifest_sha = manifest, manifest_sha
        self.root = real(manifest['run_root'], directory=True)
        import fcntl
        self.lock = (self.root/'.executor.lock').open('a+b')
        fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.group = real(manifest['cgroup_root'], directory=True)
        need(self.group.is_relative_to('/sys/fs/cgroup/ai4r-rsi-host/jobs'), 'FINITE_BENCHMARK_CGROUP_REQUIRED')
        for name in ('assets','work','claims','operations','reports','captures'):
            (self.root/name).mkdir(mode=0o711 if name in ('assets','work') else 0o700,exist_ok=True)
        self.store = RecordStore(self.root/'captures')
        self.parent_ref = self.store.put_bytes(pinned(manifest['parent']))
        self.issued = {}
        kernel = load_v18_executor()
        self.Job, self.Mount = kernel.ExecutionJob, kernel.ReadonlyMount
        def authorize(job):
            need(self.issued.get(job.job_id) == job, 'UNISSUED_FUNCTION_JOB'); return job
        def verify(mount):
            need(mount.source.is_file() and not mount.source.is_symlink()
                 and mount.source.is_relative_to(self.root/'assets')
                 and sha(mount.source.read_bytes()) == mount.ref['sha256'], 'EXACT_READONLY_FUNCTION_ASSET_REQUIRED')
        self.executor = bounded_executor(kernel.RestrictedExecutor)(workspace_root=self.root/'work',
            cgroup_root=self.group, authorize_job=authorize,
            capture=lambda raw, **kw:self.store.put_bytes(raw), executor_uid=WORKER_UID, executor_gid=WORKER_GID,
            allowed_asset_roots=[self.root/'assets'], verify_mount=verify)
        need(not self.executor.prerequisites(), 'ACTUAL_KERNEL_CONFINEMENT_PREREQUISITES_UNAVAILABLE')
        for name in ('assets','work'):
            ensure_worker_traversal(self.root,self.root/name)

    async def job(self, body, args, *, key, batch=1):
        need(len(list((self.root/'claims').glob('*.json'))) < self.m['limits']['max_jobs'], 'ROOT_JOB_BUDGET_EXHAUSTED')
        check_capacity(self.group)
        ident = 'function-' + sha(encoded([self.m['run_id'],key,sha(body)]))[:48]
        claim = self.root/'claims'/(ident+'.json')
        need(not claim.exists(), 'CONSUMED_JOB_NO_REPLAY')
        source_ref = self.store.put_bytes(body)
        input_raw, worker = encoded(args), program(self.m['function'],batch)
        input_ref, program_ref = self.store.put_bytes(input_raw), self.store.put_bytes(worker)
        test_ref = self.store.put({'schema':'ai4r-function-current-input:1','input_ref':input_ref,'batch':batch})
        assets = self.root/'assets'/ident;assets.mkdir(mode=0o755)
        work = self.root/'work'/ident;work.mkdir(mode=0o700);os.chown(work,WORKER_UID,WORKER_GID)
        mounts=[]
        for name,raw in [('body.py',body),('input.json',input_raw),('worker.py',worker)]:
            p=assets/name;p.write_bytes(raw);p.chmod(0o444)
            mounts.append(self.Mount(p,'/resources/'+name,{'id':name,'sha256':sha(raw)}))
        ensure_worker_traversal(self.root, assets/'worker.py');ensure_worker_traversal(self.root,work)
        meta,lim=self.m['worker'],self.m['limits']
        job=self.Job(job_id=ident,invocation_id=ident,contract_ref=meta['contract_ref'],run_id=self.m['run_id'],
            node_id='benchmark-only-pure-function',attempt_id=sha(encoded(key)),sequence=1,role='treatment',repeat_index=0,seed=0,
            argv=('/usr/local/bin/python3','-I','-B','/resources/worker.py'),cwd=work,
            timeout_s=lim['timeout_s'],memory_mb=lim['memory_mb'],pids_max=lim['pids_max'],
            baseline_ref=self.parent_ref,validation_ref=test_ref,environment_ref=meta['environment_ref'],
            subject_ref=source_ref,hardware_ref=meta['hardware_ref'],readonly_mounts=tuple(mounts))
        start={'schema':'ai4r-function-execution-start:1','job_id':ident,'candidate_ref':source_ref,
            'input_ref':input_ref,'program_ref':program_ref,'test_ref':test_ref,'manifest_sha256':self.manifest_sha,'key':key}
        exclusive(claim,start);start_ref=self.store.put(start)
        self.issued[ident]=job
        receipt=await self.executor.run(job)
        retirement=retire_owned_group(self.executor,job,receipt=receipt,start_ref=start_ref,store=self.store)
        receipt_ref=self.store.put(receipt)
        need(receipt.get('observed_runtime') is True, 'FUNCTION_JOB_RUNTIME_UNPROVEN')
        def rejected(reason):
            if sha(body)==self.m['parent']['sha256']: raise ValueError('PARENT_'+reason)
            raise CandidateRejected(reason)
        if receipt.get('termination_reason') != 'completed' or receipt.get('exit_code') != 0 or receipt.get('observed_limits',{}).get('admin_output_truncated'):
            rejected('FUNCTION_JOB_DID_NOT_COMPLETE')
        try:out=json.loads(self.store.read(receipt['stdout_ref']))
        except (ValueError,UnicodeError):rejected('MALFORMED_WORKER_OUTPUT')
        if not isinstance(out,dict) or set(out) not in ({'got','input_unmodified'},{'error','input_unmodified'}):
            rejected('EXACT_WORKER_OUTPUT_REQUIRED')
        wall=receipt['wall_time_s'];need(type(wall) in (int,float) and math.isfinite(wall) and wall>0,'EXTERNAL_WALL_REQUIRED')
        return out,wall,{'receipt_ref':receipt_ref,'start_ref':start_ref,'retirement':retirement}


def result_ok(checker,test,out):
    return out.get('input_unmodified') is True and (out.get('error') == test['raises'] if 'raises' in test
        else 'got' in out and checker.same(out['got'],test['expect']))


def report_base(mode, iteration, body, digest):
    return {'schema':REPORT,'mode':mode,'iteration':iteration,'candidate_sha256':sha(body),
            'manifest_sha256':digest,'scope':'benchmark_only_no_product_admission'}


async def perform(args):
    m,case,parent,checker=load_manifest(args.manifest,args.manifest_sha256)
    body=pinned({'path':args.candidate,'sha256':args.candidate_sha256})
    need(type(args.iteration) is int and 0 <= args.iteration <= 5, 'FINITE_ITERATION_REQUIRED')
    executor=Executor(m,args.manifest_sha256);root=executor.root
    name=f'{args.mode}-{args.iteration}-{sha(body)}'
    exclusive(root/'operations'/(name+'.json'),{'mode':args.mode,'iteration':args.iteration,
        'candidate_sha256':sha(body),'manifest_sha256':args.manifest_sha256})
    report=report_base(args.mode,args.iteration,body,args.manifest_sha256)
    refusal=source_check(body,m['function'],checker)
    if refusal:
        report.update(status='rejected',passed=False,reason=refusal)
    elif args.mode == 'evaluate':
        rows=[];evidence=[]
        for split in ('gate','score'):
            for n,test in enumerate(case[split]):
                oks=[]
                for trial in range(3):
                    out,wall,refs=await executor.job(body,test['args'],key=['evaluate',args.iteration,split,n,trial])
                    ok=result_ok(checker,test,out);oks.append(ok);evidence.append(refs)
                row={'id':f'{split}-{n}','split':split,'passed':all(oks),'trials_passed':sum(oks)}
                if split=='gate' and not all(oks):row['detail']=checker.describe(test,out)
                rows.append(row)
        report.update(status='passed' if all(r['passed'] for r in rows) else 'rejected',
            passed=all(r['passed'] for r in rows),passed_count=sum(r['passed'] for r in rows),case_count=len(rows),trials=3,
            gate_failures=[r for r in rows if r['split']=='gate' and not r['passed']],
            held_out_failing_ids=[r['id'] for r in rows if r['split']=='score' and not r['passed']],rows=rows,evidence=evidence)
    else:
        valid=[(f'gate-{n}',t) for n,t in enumerate(case['gate']) if 'expect' in t]
        need(valid,'VALID_GATE_TIMING_INPUT_REQUIRED')
        evaluation=root/'reports'/f'evaluate-{args.iteration}-{sha(body)}.json'
        need(evaluation.is_file(),'CORRECTNESS_BEFORE_TIMING_REQUIRED')
        ev=json.loads(evaluation.read_bytes())
        need(ev['passed'] is True and ev['manifest_sha256']==args.manifest_sha256,'PASSING_CORRECTNESS_REQUIRED')
        if args.mode=='calibrate':
            need(body==parent and args.iteration==0 and not (root/'calibration.json').exists(),'PARENT_ONLY_FRESH_CALIBRATION_REQUIRED')
            batches={};evidence=[]
            for ident,test in valid:
                batch=m['timing']['min_batch']
                for step in range(3):
                    out,wall,refs=await executor.job(parent,test['args'],key=['calibrate',ident,step],batch=batch)
                    need(result_ok(checker,test,out),'CALIBRATION_PARENT_CORRECTNESS_FAILED');evidence.append(refs)
                    if wall>=m['timing']['target_s'] or batch==m['timing']['max_batch']:break
                    batch=min(m['timing']['max_batch'],max(batch+1,math.ceil(batch*m['timing']['target_s']/wall*1.15)))
                batches[ident]=batch
            calibration={'schema':'ai4r-function-timing-calibration:1','manifest_sha256':args.manifest_sha256,
                         'parent_sha256':sha(parent),'batches':batches,'workload_source':'valid_gate_only','evidence':evidence}
            exclusive(root/'calibration.json',calibration)
            report.update(status='calibrated',passed=True,calibration=calibration)
        else:
            calibration_raw=(root/'calibration.json').read_bytes();calibration=json.loads(calibration_raw)
            need(calibration['manifest_sha256']==args.manifest_sha256 and calibration['parent_sha256']==sha(parent)
                 and set(calibration['batches'])=={i for i,t in valid},'FROZEN_CALIBRATION_REQUIRED')
            samples={i:[] for i,t in valid};evidence=[]
            for ident,test in valid:
                batch=calibration['batches'][ident]
                need(type(batch) is int and m['timing']['min_batch']<=batch<=m['timing']['max_batch'],'BOUNDED_BATCH_REQUIRED')
                for warmup in range(2):
                    for role,source in [('parent',parent),('candidate',body)]:
                        out,wall,refs=await executor.job(source,test['args'],key=['benchmark',args.iteration,ident,'warmup',warmup,role],batch=batch)
                        need(result_ok(checker,test,out),'WARMUP_CORRECTNESS_FAILED');evidence.append(refs)
                for repeat in range(11):
                    pair={}
                    ordered=[('parent',parent),('candidate',body)]
                    if repeat%2:ordered.reverse()
                    for role,source in ordered:
                        out,wall,refs=await executor.job(source,test['args'],key=['benchmark',args.iteration,ident,'pair',repeat,role],batch=batch)
                        need(result_ok(checker,test,out),'TIMING_CORRECTNESS_FAILED');evidence.append(refs);pair[role]=wall/batch
                    samples[ident].append([pair['parent'],pair['candidate']])
            stats=compare_paired_samples(samples,workload_ids=list(samples))
            if body==parent:stats['objective_met']=False
            report.update(status='measured',passed=True,self_comparison=body==parent,samples=samples,
                statistics=stats,calibration_sha256=sha(calibration_raw),evidence=evidence,
                timing='external protected process wall divided by frozen batch count; includes amortized startup')
    exclusive(root/'reports'/(name+'.json'),report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True);p.add_argument('--manifest-sha256',required=True)
    p.add_argument('--mode',choices=('evaluate','calibrate','benchmark'),required=True)
    p.add_argument('--iteration',type=int,required=True);p.add_argument('--candidate',required=True)
    p.add_argument('--candidate-sha256',required=True)
    args=p.parse_args()
    try:
        result=asyncio.run(perform(args))
    except CandidateRejected as error:
        m,case,parent,checker=load_manifest(args.manifest,args.manifest_sha256)
        body=pinned({'path':args.candidate,'sha256':args.candidate_sha256})
        result=report_base(args.mode,args.iteration,body,args.manifest_sha256)
        result.update(status='rejected',passed=False,reason=str(error),terminal_execution_observed=True)
        exclusive(Path(m['run_root'])/'reports'/f'{args.mode}-{args.iteration}-{sha(body)}.json',result)
    # Full evidence is in the report; console feedback never includes hidden inputs.
    print(json.dumps({k:v for k,v in result.items() if k not in ('evidence','rows','samples','calibration')}))


if __name__=='__main__':main()
