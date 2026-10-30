"""Protected broker integration for native Builder actions and exact snapshots."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json

from .builder_mode import builder_mode

from .builder_agent_service import BuilderAgentService
from .builder_testing import BuilderTestService, _input_ref
from .capsules.builder_loop import package
from .checks.prediction_bundle import inspect_bundle
from .contracts import ResearchError
from .environment import parse_requirements
from .pi_protocol import inspect_pi_bundle, parse_pi_output, validate_pi_request
from .state import json_bytes

BUILD_SCHEMA = 'urn:ai4r:prediction-build-receipt:4.0.0'


class BuilderAgentHost(BuilderTestService):
    """Host-owned workspaces. RPC callers cannot supply commands or test results."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sessions = {}
        self.actions = {}
        self._agent_lock = asyncio.Lock()

    def _model_action(self, binding, action, arguments, ordinal):
        starts = []
        for row in self.store.iter_records(run_id=binding.contract['run_id'], kinds=('model-call-start',)):
            start = row['record']
            if (start.get('contract_ref') == dict(binding.contract_ref)
                    and start.get('invocation_id') == binding.invocation_id
                    and start.get('execution_id') == binding.execution_id
                    and self.store.read_record(start['call_claim_ref'])['call_ordinal'] == ordinal):
                starts.append(start)
        if len(starts) != 1:
            raise ResearchError('auth', 'Action requires one protected completed model call')
        start = starts[0]
        call_ref = self.store.record_ref(start['call_id'])
        call = self.store.read_record(call_ref)
        outputs = [row for row in self.store.iter_records(run_id=binding.contract['run_id'], kinds=('model-call-output',))
                   if row['record'].get('call_id') == start['call_id']
                   and row['record'].get('invocation_id') == binding.invocation_id]
        if (call.get('outcome') != 'completed' or call.get('observed_runtime') is not True
                or call.get('id') != start['call_id']
                or call.get('contract_ref', dict(binding.contract_ref)) != dict(binding.contract_ref)  # absent on real model-call records; the protected start carries it
                or call.get('invocation_id') != binding.invocation_id
                or call.get('execution_id') != binding.execution_id
                or len(outputs) != 1 or outputs[0]['ref'] not in call.get('evidence_refs', [])):
            raise ResearchError('auth', 'Incomplete or unobserved model action')
        returned = json.loads(outputs[0]['record']['text'])
        if returned != {'action': action, 'arguments': arguments}:
            raise ResearchError('auth', 'Requested tool effect differs from the protected model action')
        return call_ref, outputs[0]['ref']

    def _inspect(self, binding, inputs, bundle):
        pins = parse_requirements(self.store.read_blob(inputs['lock']['requirements_ref']))
        raw = self.store.read_blob(inputs['validation_resource']['files'][0]['artifact_ref'])
        pi = getattr(self.adapter.scorer, 'protocol', None) == 'ai4r-pi:1'
        if pi:
            if _input_ref(binding.contract, 'validation_resource') != self.adapter.scorer.profile['public_dataset_ref']:
                raise ResearchError('auth', 'Pi task resource differs from frozen host profile')
            validate_pi_request(raw)
            checked = inspect_pi_bundle(bundle, pins)
        else:
            checked = inspect_bundle(bundle, ['accuracy'], pins)
        if checked['files']['requirements.txt'] != self.store.read_blob(inputs['lock']['requirements_ref']):
            raise ResearchError('validation', 'Requirements differ from frozen environment')
        return checked, pins, pi

    def _manifest(self, contract, files):
        bundle, encoded = package({k: files[k] for k in ('requirements.txt','poc_patch.py','run_benchmark.py')})
        archive_ref = self.store.put_blob(bundle, media_type='application/zip')
        manifest = {'schema_version': '2.0.0', 'id': 'poc_manifest',
            'blueprint_ref': _input_ref(contract, 'blueprint'), 'environment_ref': _input_ref(contract, 'lock'),
            'archive_ref': archive_ref, 'files': [{'path': name, 'artifact_ref': self.store.put_blob(raw),
                'media_type': 'text/plain' if name.endswith('.txt') else 'text/x-python',
                'audience': 'researcher'} for name, raw in encoded.items()],
            'dependencies': [{'name': k, 'version': v} for k,v in parse_requirements(encoded['requirements.txt']).items()]}
        return manifest, self.store.put_record('poc-manifest', manifest), bundle

    def _mount_files(self, files, binding, label, target):
        resource = {'schema_version':'1.0.0','id':label,'kind':'development snapshot',
            'origin':'protected Builder journal','revision':hashlib.sha256(json_bytes(files)).hexdigest(),
            'files':[{'path':k,'artifact_ref':self.store.put_blob(v.encode()),'media_type':'text/plain',
                      'audience':'authorized researcher'} for k,v in sorted(files.items())],
            'access':'read-only','license':'not stated','availability':'available',
            'environment_ref':_input_ref(binding.contract,'lock')}
        ref = self.store.put_record('resource-snapshot',resource)
        return self._mount(resource,ref,target)

    async def _check(self, contract, inputs, binding, check, files, test_name):
        try:
            manifest, manifest_ref, bundle = self._manifest(contract,files)
            _, pins, pi = self._inspect(binding,inputs,bundle)
        except (ValueError,TypeError,SyntaxError) as exc:
            return {'passed':False,'detail':'Candidate package check failed: '+str(exc)[:1000],
                    'execution_performed':False}
        except ResearchError as exc:
            if exc.code not in {'validation','invalid_output'}:raise
            return {'passed':False,'detail':exc.message[:1000],'execution_performed':False}
        if binding.invocation_id not in self.adapter._prepared:
            provision = await self.adapter.provisioner(contract,inputs,pins,binding=binding,builder_manifest_ref=manifest_ref)
            if provision['status'] != 'succeeded':
                raise ResearchError('unavailable','Development environment provisioning failed')
        environment = self.adapter._prepared[binding.invocation_id][0]
        self.adapter.environment_verifier(environment)
        candidate = self._mount_files({k:v for k,v in files.items() if k!='tests.py'},binding,'candidate','/resources/poc')
        tests = self._mount_files({'test_candidate.py':files['tests.py']},binding,'selftest','/resources/selftest')
        validation = self._mount(inputs['validation_resource'],_input_ref(contract,'validation_resource'),'/resources/validation')
        # test selection is a name passed as data to unittest, never a command.
        runner = ('import sys,unittest;sys.path.insert(0,"/resources/poc");'
                  'sys.path.insert(0,"/resources/selftest");'
                  's=unittest.defaultTestLoader.loadTestsFromName(sys.argv[1]);'
                  'n=s.countTestCases();print("AI4R_TEST_COUNT="+str(n));'
                  'r=unittest.TextTestRunner(verbosity=2).run(s);'
                  'sys.exit(0 if n>0 and r.wasSuccessful() else 1)')
        if test_name and (not isinstance(test_name,str) or not all(c.isalnum() or c in '._' for c in test_name)):
            return {'passed':False,'detail':'Invalid unittest selection','execution_performed':False}
        argv = ('/environment/bin/python','-c',runner,test_name or 'test_candidate') if check=='unit' else (
            '/environment/bin/python','/resources/poc/run_benchmark.py')
        session = self.sessions[binding.invocation_id]
        ordinal = session.inspect()['jobs']
        _, raw = await self._run(contract,inputs,binding,sequence=ordinal,ordinal=ordinal,role=check,
            argv=argv,mounts=(candidate,tests,validation),environment=environment,
            subject_ref=manifest['archive_ref'],validation_ref=validation.ref,
            hardware_ref=self.store.put_blob(json_bytes({'development_only':True})))
        passed = raw.get('exit_code')==0 and raw.get('termination_reason')=='completed'
        if passed and check=='smoke':
            stdout = self.store.read_blob(raw['stdout_ref'])
            try:
                if pi:
                    # Development validates shape; Benchmark owns correctness.
                    parse_pi_output(stdout,validate_pi_request(self.store.read_blob(inputs['validation_resource']['files'][0]['artifact_ref'])))
                else:
                    from .trusted_scoring import parse_predictions,parse_public_dataset
                    parse_predictions(stdout,parse_public_dataset(self.store.read_blob(inputs['validation_resource']['files'][0]['artifact_ref'])),
                        max_stdout_bytes=1024*1024)
            except (ValueError,ResearchError):
                passed=False
        report = {'schema':'ai4r-builder-agent-check:1','contract_ref':dict(binding.contract_ref),
            **{key:contract[key] for key in ('run_id','node_id','attempt_id')},
            'invocation_id':binding.invocation_id,'execution_id':binding.execution_id,'check':check,
            'passed':passed,'runs':[raw],'manifest_ref':manifest_ref,
            'stdout':self.store.read_blob(raw['stdout_ref'])[:2048].decode(errors='replace'),
            'stderr':self.store.read_blob(raw['stderr_ref'])[:2048].decode(errors='replace')}
        ref = self.store.append_record('builder_agent_check',report)
        return {'passed':passed,'report_ref':ref,'evidence_ref':ref,'stdout_ref':raw['stdout_ref'],
                'stderr_ref':raw['stderr_ref'],'stdout':report['stdout'],'stderr':report['stderr']}

    async def action(self, contract, inputs, *, binding, action, arguments, ordinal, model_ordinal):
        async with self._agent_lock:
            if await self.authorize_binding(binding) != binding or binding.contract != contract:
                raise ResearchError('auth','Exact live Builder invocation required')
            declaration = self.store.read_record(contract['bindings'][0]['declaration_ref'])
            if builder_mode(declaration) != 'agent':
                raise ResearchError('auth','Agent tools require the exact admitted Builder release')
            call_ref, output_ref = self._model_action(binding,action,arguments,model_ordinal)
            if binding.invocation_id not in self.sessions:
                initial = {'requirements.txt':self.store.read_blob(inputs['lock']['requirements_ref']).decode(),
                           'poc_patch.py':'','run_benchmark.py':''}
                async def execute_check(check,files,name):
                    return await self._check(contract,inputs,binding,check,files,name)
                async def read_log(ref):
                    return self.store.read_blob(ref).decode(errors='replace')[:8192]
                self.sessions[binding.invocation_id] = BuilderAgentService(initial_files=initial,
                    execute_check=execute_check,read_log=read_log,session_id=binding.invocation_id)
                self.actions[binding.invocation_id] = []
            session = self.sessions[binding.invocation_id]
            if type(ordinal) is not int or ordinal != session.inspect()['tool_calls']+1:
                raise ResearchError('auth','Agent action replay or changed sequence')
            try:
                result = await session.dispatch(action,arguments,model_ordinal)
            except BaseException as exc:
                session.stop(type(exc).__name__)
                self.store.append_record('builder_agent_stop',{
                    **{key:contract[key] for key in ('run_id','node_id','attempt_id')},
                    'contract_ref':dict(binding.contract_ref),'invocation_id':binding.invocation_id,
                    'execution_id':binding.execution_id,'ordinal':ordinal,'model_ordinal':model_ordinal,
                    'model_call_ref':call_ref,'model_output_ref':output_ref,'reason':type(exc).__name__,
                    'snapshot_sha256':session.snapshot_sha256})
                raise
            row = session.inspect()['journal'][-1]
            self.actions[binding.invocation_id].append({'ordinal':ordinal,'model_ordinal':model_ordinal,
                'action':action,'arguments':copy.deepcopy(arguments),'before_sha256':row['before_snapshot_sha256'],
                'after_sha256':row['after_snapshot_sha256'],'result':row['result'],
                'model_call_ref':call_ref,'model_output_ref':output_ref})
            self.store.append_record('builder_agent_action',{'contract_ref':dict(binding.contract_ref),
                **{key:contract[key] for key in ('run_id','node_id','attempt_id')},
                'invocation_id':binding.invocation_id,**self.actions[binding.invocation_id][-1]})
            if not result.get('submitted'):
                return result
            state = session.inspect()
            manifest,manifest_ref,bundle = self._manifest(contract,state['files'])
            checked,pins,_ = self._inspect(binding,inputs,bundle)
            checks = {}
            for key in ('compile','unit','smoke'):
                value=state['checks'][key]
                report_ref = value['report'].get('report_ref')
                if report_ref is None:
                    report_ref = self.store.append_record('builder_agent_check',{
                        **{key:contract[key] for key in ('run_id','node_id','attempt_id')},
                        'check':key,'passed':value['passed'],'snapshot_sha256':value['snapshot_sha256'],
                        'contract_ref':dict(binding.contract_ref),'invocation_id':binding.invocation_id,
                        'runs':[],'host_compilation':True})
                checks[key] = {'status':'passed' if value['passed'] else 'failed',
                    'snapshot_sha256':value['snapshot_sha256'],'report_ref':report_ref}
            journal = {'schema':'ai4r-builder-agent-execution:1','contract_ref':dict(binding.contract_ref),
                **{key:contract[key] for key in ('run_id','node_id','attempt_id')},
                'invocation_id':binding.invocation_id,'execution_id':binding.execution_id,
                'initial_files':{'requirements.txt':self.store.read_blob(inputs['lock']['requirements_ref']).decode(),
                                 'poc_patch.py':'','run_benchmark.py':'','tests.py':''},
                'actions':self.actions[binding.invocation_id],'files':state['files'],
                'snapshot_sha256':state['snapshot']['sha256'],'submitted_snapshot_sha256':state['snapshot']['sha256'],'checks':checks,
                'manifest_ref':manifest_ref,'archive_ref':manifest['archive_ref']}
            journal_ref = self.store.append_record('builder_agent_execution',journal)
            receipt = {'schema_version':'4.0.0','id':'build_receipt','manifest_ref':manifest_ref,
                'archive_ref':manifest['archive_ref'],'blueprint_ref':_input_ref(contract,'blueprint'),
                'environment_ref':_input_ref(contract,'lock'),'journal_ref':journal_ref,
                'workspace_sha256':state['snapshot']['sha256'],'submitted_snapshot_sha256':state['snapshot']['sha256'],
                'model_call_count':model_ordinal,'tool_operation_count':ordinal,'execution_job_count':state['jobs'],
                'test_report_refs':[v['report_ref'] for v in checks.values()],
                'development_only':True,'trial_executed':True,'packages_installed':bool(pins),'readiness':'READY',
                'readiness_reasons':[],'checker':'host protected agent journal','file_checks':checked['file_checks'],
                'dependencies':checked['dependencies'],'dependencies_all_pinned':True,'forbidden_scan_result':'pass'}
            ref = self.store.put_record(BUILD_SCHEMA,receipt,scope=contract)
            self.store.append_record('builder_agent_submission',{
                **{key:contract[key] for key in ('run_id','node_id','attempt_id')},
                'contract_ref':dict(binding.contract_ref),'invocation_id':binding.invocation_id,
                'journal_ref':journal_ref,'build_receipt_ref':ref,'manifest_ref':manifest_ref,
                'archive_ref':manifest['archive_ref']})
            return {'submitted':True,'manifest_ref':manifest_ref,'bundle_ref':manifest['archive_ref'],'build_receipt_ref':ref,
                'candidate_file_refs':[row['artifact_ref'] for row in manifest['files']]}
