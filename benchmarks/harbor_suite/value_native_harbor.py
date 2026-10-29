"""Harbor adapter for the real JiuwenSwarm native application.

The pinned host command invokes execute_native.py exactly once. It supplies no
completion itself and exports original native run/broker files for independent
identity and content grading. The module also runs as a standalone frozen grader.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

try:
    from harbor.agents.base import BaseAgent
except ImportError:
    BaseAgent = object

ADAPTER = 'benchmarks.harbor_suite.value_native_harbor:JiuwenSwarmNativeAgent'
SCHEMA = 'jiuwenswarm-native-harbor-host:1'
IMAGE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._/:\-]*@sha256:[a-f0-9]{64}$')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def pin(path):
    path = Path(path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Bounded original regular file required: ' + str(path))
    raw = path.read_bytes()
    if len(raw) > 128 * 1024 * 1024:
        raise ValueError('Control file exceeds finite bound')
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def load_host_config(path):
    config = read(path)
    fields = {'schema', 'task_root', 'staged_root', 'public_export', 'private_control', 'cwd',
              'command', 'control_files', 'expected_model', 'expected_effort',
              'task_sha256', 'timeout_s', 'execute_script_host', 'execute_script_argument', 'staged_argument'}
    if set(config) != fields or config['schema'] != SCHEMA:
        raise ValueError('Exact native Harbor host configuration required')
    for key in ('task_root', 'staged_root', 'public_export', 'private_control', 'cwd'):
        root = Path(config[key])
        if not root.is_absolute() or not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)):
            raise ValueError('Existing absolute non-symlink root required: ' + key)
    task_root, staged = Path(config['task_root']), Path(config['staged_root'])
    if Path(path).resolve().is_relative_to(staged.resolve()):
        raise ValueError('Host control configuration must stay outside the baseline stage')
    if Path(config['public_export']) == staged or Path(config['public_export']).is_relative_to(staged):
        raise ValueError('Public export must be separate from active native stage')
    if config['expected_model'] != 'gpt-6.1-sol' or config['expected_effort'] != 'medium':
        raise ValueError('Qualified model/effort pin required')
    if type(config['timeout_s']) is not int or not 1 <= config['timeout_s'] <= 420:
        raise ValueError('Finite native observer timeout required')
    command = config['command']
    if not isinstance(command, list) or len(command) != 5 or any(not isinstance(x, str) or not x or '\0' in x for x in command):
        raise ValueError('Explicit five-element native argv required')
    if not Path(command[0]).is_absolute() or command[1:] != [config['execute_script_argument'], 'run', '--staged', config['staged_argument']]:
        raise ValueError('Host command must invoke the pinned native run wrapper exactly once')
    if Path(config['execute_script_host']).name != 'execute_native.py':
        raise ValueError('Authentic native wrapper required')
    if not isinstance(config['control_files'], dict) or not config['control_files']:
        raise ValueError('Host executable, wrapper and stage controls must be pinned')
    required_controls = {str(Path(command[0])), config['execute_script_host'], str(staged/'spec.json'),
                         str(staged/'commands.json'), str(staged/'runtime/benchmarks/harbor_suite/native_value.py')}
    if not required_controls <= set(config['control_files']):
        raise ValueError('Native runtime control pin omitted')
    for filename, expected in config['control_files'].items():
        if pin(filename) != expected:
            raise ValueError('Pinned native control changed: ' + filename)
    spec = read(staged/'spec.json')
    if (spec.get('variant') != 'native' or spec.get('skill_dirs') != []
            or spec.get('model') != config['expected_model'] or spec.get('reasoning_effort') != config['expected_effort']):
        raise ValueError('Native spec must retain ordinary bundled skills without CC/task-skill injection')
    task = (task_root/'instruction.md').read_text(encoding='utf-8')
    if hashlib.sha256(task.encode()).hexdigest() != config['task_sha256'] or spec.get('task') != task:
        raise ValueError('Harbor instruction and actual native task must match exact bytes')
    return config


def export_originals(config, dispatch):
    source, output = Path(config['staged_root']), Path(config['public_export'])
    if list(output.iterdir()):
        raise ValueError('Native export is not empty; reuse is refused')
    selected = []
    run = source/'run'
    if run.is_dir():
        selected.extend((file, Path('run')/file.relative_to(run)) for file in run.rglob('*') if file.is_file())
    selected.extend((file, Path('broker')/file.name) for file in (source/'broker').glob('*.json'))
    selected.append((source/'spec.json', Path('spec.json')))
    inventory, total = [], 0
    for file, relative in sorted(selected):
        if file.is_symlink() or not file.resolve().is_relative_to(source.resolve()):
            raise ValueError('Native original escaped staged custody')
        if '.codex' in relative.parts or file.name == 'auth.json':
            raise ValueError('Authentication storage must never enter native export')
        raw = file.read_bytes(); total += len(raw)
        if total > 512*1024*1024 or len(inventory) >= 30000:
            raise ValueError('Original native export exceeds finite custody limit')
        target = output/relative; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        inventory.append({'path': relative.as_posix(), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    write_new(output/'host-dispatch.json', dispatch)
    write_new(output/'originals-inventory.json', {'schema': 'jiuwenswarm-native-originals:1',
        'task_sha256': config['task_sha256'], 'files': inventory,
        'scope': 'Original native run and completion broker; host credentials/private receipts/oracles excluded'})
    return output


async def dispatch(config, trial_identity, *, launcher=None):
    """One exclusive launch; no retries, repaired artifacts or generated answers."""
    control = Path(config['private_control'])
    claim_key = hashlib.sha256((config['task_sha256']+'\n'+str(Path(config['staged_root']))).encode()).hexdigest()
    claim = control/('harbor-native-claim-'+claim_key+'.json')
    write_new(claim, {'task_sha256': config['task_sha256'], 'trial_identity': trial_identity,
                      'staged_root': config['staged_root']})
    if (Path(config['staged_root'])/'run').exists():
        raise ValueError('Native stage already contains a run; no resume or implicit retry')
    result = {'schema': 'jiuwenswarm-native-harbor-dispatch:1', 'task_sha256': config['task_sha256'],
              'status': 'outcome_unknown', 'returncode': None, 'native_application': 'JiuWenSwarm',
              'expected_model': config['expected_model'], 'expected_effort': config['expected_effort']}
    launch = launcher or asyncio.create_subprocess_exec
    cancelled = None
    with (control/(claim.stem+'.stdout')).open('xb') as stdout, (control/(claim.stem+'.stderr')).open('xb') as stderr:
        process = None
        try:
            options={'cwd':config['cwd'],'stdout':stdout,'stderr':stderr}
            if os.name=='nt':options['creationflags']=subprocess.CREATE_NO_WINDOW
            process = await launch(*config['command'], **options)
            result['returncode'] = await asyncio.wait_for(process.wait(), config['timeout_s'])
            result['status'] = 'observer_returned'
        except (asyncio.TimeoutError, asyncio.CancelledError) as error:
            cancelled = error
            # Killing an observer is not proof its Docker child stopped. Preserve
            # unknown status and forbid a retry via the exclusive claim.
            if process is not None and process.returncode is None:
                process.terminate()
                try:await asyncio.wait_for(process.wait(), 10)
                except asyncio.TimeoutError:pass
        except OSError as error:
            result.update(status='launch_failed', error_type=type(error).__name__)
    if result['status']=='observer_returned':
        for filename,expected in config['control_files'].items():
            if pin(filename)!=expected:
                result.update(status='control_changed_after_dispatch',changed_control=filename)
                break
    folder = export_originals(config, result)
    return folder, result, cancelled


class JiuwenSwarmNativeAgent(BaseAgent):
    def __init__(self, *args, host_config=None, host_config_sha256=None, **kwargs):
        self._path, self._sha = host_config, host_config_sha256
        super().__init__(*args, **kwargs)

    @staticmethod
    def name():return 'jiuwenswarm-native-skills'

    def version(self):return '1'

    async def setup(self, environment):
        self._path = self._path or os.environ.get('AI4R_NATIVE_HARBOR_CONFIG')
        self._sha = self._sha or os.environ.get('AI4R_NATIVE_HARBOR_CONFIG_SHA256')
        if not self._path or not self._sha or pin(self._path)['sha256'] != self._sha:
            raise ValueError('Pinned host-only real-native configuration required')
        self._config = load_host_config(self._path)

    async def run(self, instruction, environment, context):
        if pin(self._path)['sha256'] != self._sha:
            raise ValueError('Native host configuration changed')
        config = load_host_config(self._path)
        if instruction != (Path(config['task_root'])/'instruction.md').read_text(encoding='utf-8'):
            raise ValueError('Native instruction changed')
        folder, receipt, cancelled = await dispatch(config, str(Path(self.logs_dir).resolve()))
        await environment.upload_dir(source_dir=folder, target_dir='/app/native-originals')
        context.metadata = {'native_application': 'JiuWenSwarm', 'native_host_dispatch': receipt,
                            'scope': 'Real native application; ordinary skills and tools; no CC verifier'}
        if cancelled is not None:raise cancelled


def joined_native_evidence(root, task):
    """Independent original request/response/model/effort and usage population join."""
    root = Path(root); inventory = read(root/'originals-inventory.json')
    if inventory.get('task_sha256') != task['task_sha256']:
        raise ValueError('Original native inventory belongs to another task')
    for row in inventory['files']:
        path = Path(row['path'])
        if path.is_absolute() or '..' in path.parts or pin(root/path) != {'sha256': row['sha256'], 'bytes': row['bytes']}:
            raise ValueError('Original native inventory mismatch')
    dispatch_record = read(root/'host-dispatch.json')
    if dispatch_record.get('status') != 'observer_returned' or dispatch_record.get('task_sha256') != task['task_sha256']:
        raise ValueError('Native host did not return a reconciled original run')
    run = root/'run'; spec = read(root/'spec.json'); result = read(run/'result.json')
    if pin(root/'spec.json')['sha256'] != task['native_spec_sha256'] or read(run/'assignment.json') != spec:
        raise ValueError('Actual native assignment differs from frozen spec')
    if hashlib.sha256(spec['task'].encode()).hexdigest() != task['task_sha256']:
        raise ValueError('Native received different task bytes')
    if result.get('native_application') != 'JiuWenSwarm':
        raise ValueError('Output is not actual native application evidence')
    for filename,expected in task.get('public_inputs',{}).items():
        if Path(filename).name!=filename or pin(run/'project'/filename)!=expected:
            raise ValueError('Actual native public input differs from the frozen task')
    requests, responses = sorted((run/'evidence').glob('completion-*-request.json')), sorted((run/'evidence').glob('completion-*-response.json'))
    if not requests or len(requests) != len(responses) or len(requests) != result.get('model_calls'):
        raise ValueError('Native actual completion population does not close')
    usages, seen = [], set()
    canonical = lambda value: json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    for sent_path, response_path in zip(requests,responses):
        sent, response = read(sent_path), read(response_path)
        ident = response.get('request_id')
        if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident) or ident in seen:
            raise ValueError('Native completion ID absent or duplicated')
        seen.add(ident)
        broker_sent, broker_response = read(root/'broker'/(ident+'.request.json')), read(root/'broker'/(ident+'.response.json'))
        if (response.get('status') != 'completed' or response.get('identity',{}).get('effective') != task['expected_model']
                or response.get('identity',{}).get('basis') in (None,'unknown','requested_only')
                or response.get('reasoning_effort') != task['expected_effort']
                or broker_sent.get('request_id') != ident
                or broker_sent.get('model') != task['expected_model'] or broker_sent.get('reasoning_effort') != task['expected_effort']
                or canonical(response) != canonical(broker_response)
                or canonical(json.loads(broker_sent['prompt'].rsplit('\n',1)[-1])) != canonical({k:sent[k] for k in ('messages','tools')})):
            raise ValueError('Native original wire/model/effort does not join')
        usages.append(response.get('usage') or {})
    totals={}
    for key in ('input_tokens','output_tokens','cached_input_tokens'):
        values=[u.get(key) for u in usages]
        totals[key]=sum(values) if all(type(v) is int and v>=0 for v in values) else None
    return {'model_calls':len(usages),'usage':totals,'selected_tool_calls':result.get('selected_tool_calls'),
            'terminal_status':result.get('status'),'identity_verified':True}


def original_verdict(root):
    root=Path(root);candidates=[]
    for path in sorted((root/'run/project').glob('*.json')):
        try:value=read(path)
        except ValueError:continue
        if isinstance(value,dict) and value.get('id')=='evaluation_verdict':candidates.append((path,value))
    if candidates:
        unique={json.dumps(v,sort_keys=True,separators=(',',':')) for _,v in candidates}
        if len(unique)!=1:raise ValueError('Conflicting original verdict artifacts')
        path,value=candidates[0]
        return value,{'id':'original-native:'+path.relative_to(root).as_posix(),'sha256':pin(path)['sha256']}
    events=root/'run/events.jsonl'
    for ordinal,line in enumerate(events.read_text(encoding='utf-8').splitlines(),1):
        payload=json.loads(line).get('payload') or {}
        if payload.get('event_type')!='chat.final' or not isinstance(payload.get('content'),str):continue
        text=payload['content'].strip()
        if text.startswith('```json\n') and text.endswith('\n```'):text=text[8:-4]
        try:value=json.loads(text)
        except ValueError:continue
        if isinstance(value,dict) and value.get('id')=='evaluation_verdict':
            candidates.append((ordinal,value))
    if len(candidates)!=1:raise ValueError('Original final verdict absent or ambiguous; prose is not reconstructed')
    ordinal,value=candidates[0]
    return value,{'id':'original-native:run/events.jsonl:'+str(ordinal),'sha256':pin(events)['sha256']}


def grade(root, tests, output):
    root,tests,output=Path(root),Path(tests),Path(output)
    task=read(tests/'task.json');report={'schema':'jiuwenswarm-native-harbor-assessment:1',
        'case_id':task['case_id'],'variant_id':task['variant_id'],'status':'unavailable',
        'identity_verified':False,'content_correct':None,'usable_completion':False,'usage':None,'checks':[],'errors':[]}
    try:
        identity=joined_native_evidence(root,task);report.update(identity_verified=True,usage=identity)
        value,output_ref=original_verdict(root)
        spec=importlib.util.spec_from_file_location('frozen_native_oracle',tests/'oracle.py')
        oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
        evidence={'variant_id':task['variant_id'],'records':[{'kind':'output','port':'evaluation_verdict',
            'record':value,'ref':output_ref}]}
        evaluated=oracle.evaluate(evidence,read(tests/'criteria.json'));report.update(evaluated)
        report['content_correct']=False if any(c['status']=='fail' for c in report['checks']) else None if any(c['status']=='unavailable' for c in report['checks']) else True
        report['usable_completion']=report['content_correct'] is True and identity['terminal_status']=='completed'
        report['status']='passed' if report['content_correct'] is True else 'failed' if report['content_correct'] is False else 'unavailable'
    except (OSError,ValueError,KeyError,TypeError) as error:report['errors'].append(str(error))
    output.mkdir(parents=True,exist_ok=True)
    (output/'assessment.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (output/'reward.json').write_text(json.dumps({'case_correctness':int(report['content_correct'] is True),'usable_completion':int(report['usable_completion']),'identity_verified':int(report['identity_verified'])})+'\n',encoding='utf-8')
    return report


def prepare_task(destination, staged, case_root, *, python_image):
    """Freeze a real-native Harbor task. No process, model or Docker launch."""
    destination,staged,case_root=Path(destination).absolute(),Path(staged).absolute(),Path(case_root).absolute()
    if destination.exists() or not destination.parent.is_dir() or not IMAGE.fullmatch(python_image):
        raise ValueError('Fresh task bundle and digest-pinned Python image required')
    spec=read(staged/'spec.json');task_text=spec['task']
    meta={'schema':'jiuwenswarm-native-harbor-task:1','case_id':'ccv05-evaluate','variant_id':'primary',
          'task_sha256':hashlib.sha256(task_text.encode()).hexdigest(),'native_spec_sha256':pin(staged/'spec.json')['sha256'],
          'expected_model':spec['model'],'expected_effort':spec['reasoning_effort'],'scope':'real_native_application; deterministic content with semantic judgment separate'}
    meta['public_inputs']={f.name:pin(f) for f in sorted((staged/'inputs').iterdir()) if f.is_file()}
    config='''schema_version = "1.4"
artifacts = ["/app/native-originals"]
[metadata]
classification = "targeted_native_jiuwenswarm_development"
split = "development"
[agent]
timeout_sec = 420.0
[environment]
cpus = 1
memory_mb = 256
storage_mb = 2048
network_mode = "no-network"
[verifier]
timeout_sec = 180.0
environment_mode = "separate"
[verifier.environment]
cpus = 1
memory_mb = 512
storage_mb = 2048
network_mode = "no-network"
'''
    files={'instruction.md':task_text.encode(),'task.toml':config.encode(),
           'environment/Dockerfile':('FROM '+python_image+'\nWORKDIR /app\n').encode(),
           'environment/.dockerignore':b'*\n!Dockerfile\n!.dockerignore\n',
           'tests/task.json':json.dumps(meta,indent=2).encode(),
           'tests/criteria.json':(case_root/'referee/criteria.json').read_bytes(),
           'tests/oracle.py':(case_root/'oracle.py').read_bytes(),
           'tests/value_native_harbor.py':Path(__file__).read_bytes(),
           'tests/Dockerfile':('FROM '+python_image+'\nWORKDIR /tests\nCOPY . /tests/\nRUN chmod 0555 /tests/test.sh\n').encode(),
           'tests/test.sh':b'#!/bin/sh\nset -eu\npython /tests/value_native_harbor.py grade --evidence /app/native-originals --tests /tests --output /logs/verifier\n',
           'tests/.dockerignore':b'*\n!task.json\n!criteria.json\n!oracle.py\n!value_native_harbor.py\n!Dockerfile\n!test.sh\n!.dockerignore\n'}
    task_root=destination/'task';task_root.mkdir(parents=True)
    for name,raw in files.items():
        target=task_root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    write_new(destination/'frozen-task.json',{'metadata':meta,'files':{name:{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)} for name,raw in files.items()}})
    write_new(destination/'job.json',{'job_name':'native-ccv05-primary','jobs_dir':str(destination/'jobs'),
        'n_attempts':1,'n_concurrent_trials':1,'retry':{'max_retries':0},'environment':{'type':'docker','delete':False},
        'agents':[{'name':None,'import_path':ADAPTER,'model_name':spec['model']}],'tasks':[{'path':str(task_root)}]})
    return task_root


def freeze_host_config(destination, *, bundle, staged, execute_host, execute_argument, staged_argument,
                       executable, cwd, public_export, private_control):
    bundle,staged=Path(bundle).absolute(),Path(staged).absolute()
    destination=Path(destination).absolute();task_root=bundle/'task'
    for folder in (Path(public_export),Path(private_control)):folder.mkdir(parents=True,exist_ok=True)
    meta=read(task_root/'tests/task.json')
    controls=[Path(executable),Path(execute_host),staged/'spec.json',staged/'commands.json',
              staged/'runtime/benchmarks/harbor_suite/native_value.py']
    controls += [f for f in (staged/'inputs').iterdir() if f.is_file()]
    controls += [f for f in task_root.rglob('*') if f.is_file()]
    controls += [bundle/'frozen-task.json',Path(__file__)]
    value={'schema':SCHEMA,'task_root':str(task_root),'staged_root':str(staged),
           'public_export':str(Path(public_export).absolute()),'private_control':str(Path(private_control).absolute()),
           'cwd':str(Path(cwd).absolute()),'command':[str(Path(executable).absolute()),str(execute_argument),'run','--staged',str(staged_argument)],
           'execute_script_host':str(Path(execute_host).absolute()),'execute_script_argument':str(execute_argument),
           'staged_argument':str(staged_argument),'control_files':{str(f):pin(f) for f in controls},
           'expected_model':meta['expected_model'],'expected_effort':meta['expected_effort'],
           'task_sha256':meta['task_sha256'],'timeout_s':390}
    for root in (bundle,staged,Path(public_export).absolute(),Path(private_control).absolute()):
        if destination.is_relative_to(root):raise ValueError('Host config must remain outside task/export/private receipt roots')
    write_new(destination,value);load_host_config(destination)
    job=read(bundle/'job.json');job['agents'][0]['kwargs']={'host_config':str(destination),'host_config_sha256':pin(destination)['sha256']}
    write_new(bundle/'job-host.json',job)
    return destination


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['grade'])
    parser.add_argument('--evidence',type=Path,required=True);parser.add_argument('--tests',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();result=grade(a.evidence,a.tests,a.output);print(json.dumps({'status':result['status'],'content_correct':result['content_correct']}))
if __name__=='__main__':main()
