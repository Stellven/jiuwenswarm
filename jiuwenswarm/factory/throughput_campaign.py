"""Bounded native STRATA throughput comparisons with a host-owned frozen judge."""
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

from .contract import atomic_json
from .engine_adapters import validate_contract, sha, inspect_assets, protocol, parse_protocol, verify_cell_evidence
from .jobs import Jobs, metadata
from .store import Store, encoded

ADAPTER = 'native-throughput-v1'
ORDERS = {'aa': 'AA', 'screen': 'AB', 'confirm': 'ABBA'}


def placement(stderr, budget):
    budgets = re.findall(r'^ds4: fixed expert budget requested=(\d+) effective=(\d+) safe=(\d+) bytes$', stderr, re.M)
    layers = re.findall(r'^ds4: fixed placement layer=(\d+) experts=(\d+) resident=(\d+) fnv1a64=([a-f0-9]{16})$', stderr, re.M)
    total = re.findall(r'^ds4: fixed placement layers=(\d+) fnv1a64=([a-f0-9]{16})$', stderr, re.M)
    if (len(budgets) != 1 or budgets[0][:2] != (budget, budget) or int(budgets[0][2]) < int(budget)
            or len(layers) != 40 or [int(v[0]) for v in layers] != list(range(40))
            or any(v[1] != '384' or not 0 <= int(v[2]) <= 384 for v in layers)
            or len(total) != 1 or total[0][0] != '40'):
        raise ValueError('Complete fixed expert placement evidence required')
    return {'layers': layers, 'aggregate': total[0]}


def judge(stage, cells, target, max_spread):
    """Exact tokens/finish and placement before timing; no model-provided verdict."""
    if [v['arm'] for v in cells] != list(ORDERS[stage]):
        raise ValueError('Comparison order or process count differs')
    identity = cells[0]['placement']
    reference = [(r['ids'], r['finish']) for r in cells[0]['requests']]
    exact = len(reference) == 2 and reference[0] == reference[1] and all([(r['ids'], r['finish']) for r in c['requests']] == reference for c in cells)
    fixed = all(c['placement'] == identity for c in cells)
    # Each process has an unscored warmup followed by the fixed measurement.
    rates = {arm: [c['requests'][1]['decode_tps'] for c in cells if c['arm'] == arm] for arm in 'AB'}
    a = rates['A']; b = rates['B']
    stable = max(a) / min(a) - 1 <= max_spread
    gain = statistics.mean(b) / statistics.mean(a) - 1 if b else None
    conservative = min(b) / max(a) - 1 if b else None
    valid = exact and fixed and stable
    verdict = ('baseline_valid' if valid else 'inconclusive') if stage == 'aa' else (
        ('target_met' if stage == 'confirm' else 'screen_positive') if valid and conservative >= target
        else 'target_not_met' if valid else 'inconclusive')
    return dict(verdict=verdict, execution_complete=True, stage=stage,
        gates={'exact_tokens_and_finish': exact, 'fixed_placement': fixed, 'baseline_timing_stable': stable},
        baseline_tokens_s=statistics.mean(a), candidate_tokens_s=statistics.mean(b) if b else None,
        relative_gain=gain, conservative_relative_gain=conservative, target_relative_gain=target,
        process_tokens_s=rates, promotion_authorized=False,
        limitations=['Fixed workload decode throughput only; no task accuracy or general model score.',
                     'Screen results are exploratory; target_met requires a separate ABBA confirmation.',
                     'Small process sample; no population confidence interval claimed.'])


class Campaign:
    def __init__(self, store, task_id):
        self.store, self.task_id = store, task_id
        self.task = store.get_task(task_id)
        self.policy = self.task['constraints']['throughput_campaign']
        self.jobs = Jobs(store)
        self.root = store.home / 'throughput-spool'
        self.root.mkdir(exist_ok=True)

    def owned(self, attempt_id):
        attempt = self.store.read(self.task_id, attempt_id)
        if attempt['request'].get('adapter') != ADAPTER:
            raise ValueError('Not a throughput attempt owned by this task')
        return attempt

    def submit(self, request, idem_key):
        if set(request) - {'stage','build_attempt_id','environment','arguments'}:
            raise ValueError('Unknown candidate fields')
        stage = request['stage']
        if stage not in ORDERS:
            raise ValueError('Expected aa, screen or confirm')
        if time.time() >= self.policy['deadline']:
            raise ValueError('Throughput campaign deadline expired')
        if not {'process.exec','gpu.use'} <= set(self.task['allowed_effects']):
            raise ValueError('Throughput execution requires operator process/GPU grants')
        contract = validate_contract(copy.deepcopy(self.policy['contract']))
        candidate = copy.deepcopy(contract)
        for category, allowed in [('environment','allowed_environment'), ('arguments','allowed_arguments')]:
            changes = request.get(category, {})
            if not isinstance(changes, dict) or any(k not in self.policy[allowed] or v not in self.policy[allowed][k] for k,v in changes.items()):
                raise ValueError('Candidate changes exceed frozen operator envelope')
            for key, value in changes.items():
                if category == 'environment':
                    candidate['workload']['environment'][key] = value
                else:
                    argv = candidate['workload']['argv']
                    if argv.count(key) != 1:
                        raise ValueError('Ambiguous candidate argument')
                    argv[argv.index(key)+1] = value
        validate_contract(candidate)
        image = self.policy['baseline_image']
        build_id = request.get('build_attempt_id')
        if build_id:
            from .builder import Builder
            from .manager import Manager
            built = Builder(self.store).status(build_id)
            if built['task_id'] != self.task_id or built['state'] != 'succeeded':
                raise ValueError('Candidate needs a successful same-task build')
            receipt = json.loads(self.store.artifact_bytes(self.task_id, build_id + ':receipt'))
            image = {'tag': built['request']['tag'], 'id': receipt['image_id']}
            Manager(self.store, self.store.home/'lab-spool').admit(self.task_id, image, build_id)
        if stage == 'aa' and (build_id or request.get('environment') or request.get('arguments')):
            raise ValueError('A/A must be the unchanged operator baseline')
        signature = hashlib.sha256(encoded(dict(image=image, contract=candidate)).encode()).hexdigest()
        # Preparation and repeated submission are idempotent; no new budgets on replay.
        with (self.root / 'admission.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            old = self.store._db.execute('SELECT attempt_id,request FROM attempts WHERE task_id=? AND idem_key=?', (self.task_id, idem_key)).fetchone()
            if old:
                if json.loads(old['request']).get('candidate_request') != request:
                    raise ValueError('Idempotency key names different candidate inputs')
                return self.status(old['attempt_id'])
            attempts = [self.store._decode('attempts',r) for r in self.store._db.execute('SELECT * FROM attempts WHERE task_id=?', (self.task_id,))]
            previous = []
            used = 0
            for a in attempts:
                if a['request'].get('adapter') == ADAPTER:
                    used += len(ORDERS[a['request']['stage']])
                    obs = self.store._db.execute('SELECT "values" FROM observations WHERE task_id=? AND obs_id=?', (self.task_id,a['attempt_id']+':throughput')).fetchone()
                    if obs:
                        previous.append((a['request'], self.result(a['attempt_id'])['analysis']))
            if used + len(ORDERS[stage]) > self.policy['max_gpu_processes']:
                raise ValueError('Campaign GPU process allowance exhausted')
            if stage != 'aa' and not any(v['verdict']=='baseline_valid' for _,v in previous):
                raise ValueError('Collect a valid fresh A/A baseline first')
            if stage == 'confirm' and not any(r['signature']==signature and v['verdict']=='screen_positive' for r,v in previous):
                raise ValueError('Confirmation needs a collected positive same-candidate screen')
            record = dict(adapter=ADAPTER, stage=stage, candidate_request=request, signature=signature,
                policy=self.policy, contracts={'A':contract,'B':candidate}, images={'A':self.policy['baseline_image'],'B':image},
                code={name:sha(Path(__file__).with_name(name)) for name in ('throughput_campaign.py','engine_adapters.py','strata_lab.py','lab_recorder.py','lab_lifecycle.py')})
            config = self.root / (hashlib.sha256(encoded(record).encode()).hexdigest()+'.json')
            atomic_json(config, record)
            argv = [os.environ.get('FACTORY_HOST_PYTHON',sys.executable), '-m', 'jiuwenswarm.factory.throughput_campaign',
                    '--task',self.task_id,'--attempt','{attempt_id}','--config',str(config)]
            return self.jobs.submit(self.task_id,'lab',record,idem_key,'gpu',argv,
                min(1800, len(ORDERS[stage])*(contract['limits']['timeout_s']+60)),
                {'FACTORY_HOME':str(self.store.home),'PYTHONPATH':str(Path(__file__).resolve().parents[2])})

    def status(self, attempt_id):
        self.owned(attempt_id)
        attempt = self.jobs.status(attempt_id)
        if attempt['state'] in {'succeeded','failed','cancelled'} and attempt['cleanup_state'].startswith('process_groups_reaped'):
            from .lab_lifecycle import inspect_owned, load_intent
            try:
                paths = list((self.root/attempt_id).glob('cell-*/intent.json'))
                if any(inspect_owned(load_intent(p.parent)) is not None for p in paths):
                    return attempt
                attempt = metadata(self.store, attempt, cleanup_state='reaped' if paths else 'no_container_created')
            except (ValueError,OSError,RuntimeError):
                pass
        return attempt

    def cancel(self, attempt_id):
        self.owned(attempt_id)
        attempt = self.jobs.cancel(attempt_id)
        if attempt['state'] in {'succeeded','failed','cancelled'} and attempt['cleanup_state'].startswith('process_groups_reaped'):
            from .lab_lifecycle import recover_run, inspect_owned, load_intent
            for path in (self.root/attempt_id).glob('cell-*/intent.json'):
                if inspect_owned(load_intent(path.parent)) is not None:
                    recover_run(path.parent,reason='workflow_cancel',seal=False)
        return self.status(attempt_id)

    def result(self, attempt_id):
        attempt = self.status(attempt_id)
        if attempt['state'] not in {'succeeded','failed','cancelled'}:
            return dict(attempt_id=attempt_id,state=attempt['state'],analysis=None)
        root = self.root/attempt_id
        try:
            if attempt['state'] != 'succeeded':
                raise ValueError('GPU campaign did not complete')
            manifest = json.loads((root/'manifest.json').read_text())
            actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name!='manifest.json' and not p.name.endswith('.lock')}
            if set(manifest) != actual:
                raise ValueError('Manifest coverage differs')
            if any(sha(root/name)!=digest for name,digest in manifest.items()):
                raise ValueError('Raw evidence changed')
            recorded=json.loads((root/'request.json').read_text())
            if recorded!=attempt['request']:
                raise ValueError('Worker request differs from admitted request')
            cells=[]
            for i,arm in enumerate(ORDERS[recorded['stage']]):
                cell=root/f'cell-{i}-{arm}';contract=recorded['contracts'][arm]
                content={'cell/'+str(p.relative_to(cell)):p.read_bytes() for p in cell.rglob('*') if p.is_file()}
                verify_cell_evidence(content,dict(contract=contract,admission={'image':recorded['images'][arm]}))
                report=json.loads((cell/'report.json').read_text())
                if not report['container_removed'] or not report['quiescent'] or report['reason']!='completed':
                    raise ValueError('Container completion/cleanup incomplete')
                before=json.loads((root/f'assets-{i}-before.json').read_text());after=json.loads((root/f'assets-{i}-after.json').read_text())
                if before!=after or before!=inspect_assets(contract):
                    raise ValueError('Pinned model assets changed')
                stderr=(cell/'stderr.log').read_text()
                parsed=parse_protocol((cell/'stdout.log').read_text(),stderr,contract)
                cells.append(dict(arm=arm, requests=parsed['requests'],placement=placement(stderr,contract['workload']['environment']['DS4_EXPERT_BUDGET_BYTES'])))
            analysis=judge(recorded['stage'],cells,recorded['policy']['target_relative_gain'],recorded['policy']['max_baseline_spread'])
            analysis['verification']={'raw_hashes':True,'independent_parse':True,'exact_boundary':True,'manifest_sha256':sha(root/'manifest.json')}
        except (ValueError,KeyError,OSError,RuntimeError) as error:
            analysis=dict(verdict='inconclusive',execution_complete=False,error=str(error))
        obs_id=attempt_id+':throughput'
        if not self.store._db.execute('SELECT 1 FROM observations WHERE task_id=? AND obs_id=?',(self.task_id,obs_id)).fetchone():
            refs=[]
            for name in ('request.json','manifest.json','worker.json'):
                if (root/name).is_file():
                    art=self.store.put_artifact(self.task_id,attempt_id+':'+name,root/name,'application/json',attempt_id);refs.append(art['artifact_id'])
            self.store.append_observation(self.task_id,dict(obs_id=obs_id,kind='throughput_comparison',values=analysis,source_artifacts=refs,
                host_run={'attempt_id':attempt_id},limitations='Frozen-workload throughput comparison; source evidence retained in '+str(root)))
        return dict(attempt_id=attempt_id,state=attempt['state'],analysis=analysis,evidence_refs=[obs_id])


def validate_acceptance(store, task_id, evidence_ids):
    campaign = Campaign(store, task_id)
    for ref in evidence_ids:
        if not isinstance(ref, str) or not ref.endswith(':throughput'):
            continue
        result = campaign.result(ref.removesuffix(':throughput'))
        if result['analysis'].get('verdict') == 'target_met' and result['analysis'].get('stage') == 'confirm':
            if campaign.status(result['attempt_id'])['cleanup_state'] != 'reaped':
                raise ValueError('Confirmation resource cleanup is incomplete')
            return {'evidence_id': ref, 'analysis': result['analysis']}
    raise ValueError('Acceptance requires cited independently reverified ABBA confirmation')


def worker(home, task_id, attempt_id, request):
    from .lab_recorder import run_container, host_available
    from .targets import validate_image
    from .lab_runner import inspect_image
    root=Path(home)/'throughput-spool'/attempt_id;root.mkdir(exist_ok=False)
    atomic_json(root/'request.json',request)
    outcome={'execution_outcome':'failed'}
    try:
        with Store(home) as store:
            if store.read(task_id,attempt_id)['request']!=request:
                raise ValueError('Attempt request differs')
        for name,digest in request['code'].items():
            if sha(Path(__file__).with_name(name))!=digest:
                raise ValueError('Admitted worker implementation changed')
        for i,arm in enumerate(ORDERS[request['stage']]):
            if time.time()>=request['policy']['deadline']:
                raise ValueError('Campaign deadline elapsed')
            gpu=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
            if gpu or host_available()<108*2**30:
                raise ValueError('GPU busy or host memory admission failed')
            c=validate_contract(request['contracts'][arm]);work=c['workload'];limits=c['limits'];image=request['images'][arm]['id']
            validate_image('spark-gb10',inspect_image(image),'spark-gb10')
            atomic_json(root/f'assets-{i}-before.json',inspect_assets(c))
            result=run_container(['/opt/strata/strata-dsv41',*work['argv'],'--profile-readonly','--serve'],
                output=root/f'cell-{i}-{arm}',image=image,mounts=[(work['pack'],work['pack']),(work['model_root'],work['model_root'])],
                gpu=True,environment=work['environment'],protocol=protocol(c),timeout_s=limits['timeout_s'],
                guard_gib=limits['guard_gib'],memory_bytes=limits['memory_bytes'],cpus=limits['cpus'],lease_root=Path(home).parent/'lab-lease')
            atomic_json(root/f'assets-{i}-after.json',inspect_assets(c))
            if result['reason']!='completed' or not result['container_removed'] or not result['quiescent']:
                raise ValueError('GPU process incomplete')
        outcome={'execution_outcome':'ok'}
    except Exception as error:
        outcome['error']=type(error).__name__+': '+str(error)
    atomic_json(root/'worker.json',outcome)
    atomic_json(root/'manifest.json',{str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and p.name!='manifest.json' and not p.name.endswith('.lock')})
    return 0 if outcome['execution_outcome']=='ok' else 1


def main():
    p=argparse.ArgumentParser()
    for name in ('task','attempt','config'):p.add_argument('--'+name,required=True)
    a=p.parse_args();return worker(os.environ['FACTORY_HOME'],a.task,a.attempt,json.loads(Path(a.config).read_text()))


if __name__=='__main__':
    raise SystemExit(main())
