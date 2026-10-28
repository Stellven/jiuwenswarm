"""Once-only metadata assembly for the sealed public development Core.

Uses canonical uploads/intake, Library, checking admissions, CapsuleRunner and
the existing finite runner's ContractFactory composition. Never dispatches.
"""
from __future__ import annotations
import argparse
import asyncio
import importlib.util
import inspect
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sibling(name):
    spec = importlib.util.spec_from_file_location('development_prepare_'+name,HERE/(name+'.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value


seed = sibling('rsi_development_seed')
development = sibling('rsi_development_run')
FIELDS = {'schema','id','seed_input','seed_receipt','binding_ref','principal','request_text'}


def public_documents(materials, request_text):
    document=seed.encoded({'schema':'ai4r-rsi-authorized-development-context:1','security_campaigns':'DEFERRED',
        'qualification':False,'purpose':request_text,
        'originals':[{'ref':pin,'utf8':raw.decode('utf8')} for pin,raw in materials.values()]})
    # One canonical upload retains every original Ref/UTF8 mapping. Individual
    # duplicate uploads would multiply intake refs without adding authority.
    result={'development-context.txt':document}
    seed.need(all(len(raw)<=4*1024*1024 for raw in result.values()),'PUBLIC_DOCUMENT_EXCEEDS_UPLOAD_BOUND')
    return result


def public_closure_bound(materials, request_text):
    documents=public_documents(materials,request_text)
    known={seed.encoded(pin) for pin,_ in materials.values()}
    for raw in (request_text.encode('utf8'),*documents.values()):
        digest=seed.digest(raw)
        known.add(seed.encoded({'id':'blob:'+digest,'sha256':digest}))
    # The canonical qualified-intake record has a fresh captured identity.
    seed.need(len(known)+1<=96,'PUBLIC_MODEL_CLOSURE_EXCEEDS_AUTHORIZATION_BOUND')
    return len(known)+1


def reject_checking_corpus(materials, corpus_refs):
    forbidden={pin['sha256'] for pin in corpus_refs}
    seed.need(not forbidden.intersection(pin['sha256'] for pin,_ in materials.values()),'CHECKING_CORPUS_CANNOT_ENTER_INTAKE')


def intake_source_pins():
    from jiuwenswarm.research import uploads,intake,operator_config
    return {module.__name__:seed.digest(Path(inspect.getsourcefile(module)).read_bytes())
            for module in (uploads,intake,operator_config)}


def project_host_binding(binding,workspace_id):
    fields={'configuration_ref','model_selection_profile_ref','deployment_ref','workspace_id','protected_options','host_id'}
    seed.need(isinstance(binding,dict) and set(binding)==fields and binding['workspace_id']==workspace_id
        and isinstance(binding['host_id'],str) and 0<len(binding['host_id'])<=256
        and binding['protected_options'].get('development_builtin_catalog') is False,'EXACT_PROTECTED_HOST_BINDING_REQUIRED')
    return {key:value for key,value in binding.items() if key!='host_id'},binding['host_id']


def read_input(input_path):
    value = seed.parse(seed.read(input_path))
    seed.need(isinstance(value,dict) and set(value)==FIELDS
        and value['schema']=='ai4r-rsi-development-prepare-input:1','CLOSED_PREPARATION_INPUT_REQUIRED')
    seed.ref(value['binding_ref'])
    seed.need(isinstance(value['request_text'],str) and 0<len(value['request_text'])<=4096,'FINITE_VISIBLE_REQUEST_REQUIRED')
    actor = value['principal']
    seed.need(isinstance(actor,dict) and set(actor)=={'account_id','workspace_id'}
        and all(isinstance(x,str) and 0<len(x)<=256 for x in actor.values()),'EXPLICIT_ISOLATED_PRINCIPAL_REQUIRED')
    complete = seed.read_completed_seed(value['seed_receipt'])
    original = seed.parse(seed.read(value['seed_input']['path']))
    seed.need(seed.digest(seed.read(value['seed_input']['path']))==value['seed_input']['sha256']
        and seed.digest(seed.encoded(original))==complete['input_sha256']
        and value['id']==complete['id']==original['id'],'EXACT_SEED_INPUT_AND_COMPLETION_REQUIRED')
    packet,materials = seed.packet_materials(original['material_packet'])
    seed.need(len(materials)<=96,'PUBLIC_UPLOAD_CLOSURE_EXCEEDS_AUTHORIZATION_BOUND')
    return value,complete,original,packet,materials


def snapshot(input_path):
    value,complete,original,packet,materials=read_input(input_path)
    root=Path(complete['destination']['isolation_root'])
    output=root/'development-preparation.json'
    seed.need(not output.exists() and not Path(input_path).with_name('claim.json').exists()
        and not Path(input_path).with_name('complete.json').exists(),'PREPARATION_ALREADY_ISSUED_NO_REPLAY')
    closure_bound=public_closure_bound(materials,value['request_text'])
    reader=seed.SourceReader(complete['destination']['core_root'])
    try:
        raw_binding=reader.read_record(value['binding_ref'])
        binding,host_id=project_host_binding(raw_binding,value['principal']['workspace_id'])
        imported=reader.read_record(complete['imported_historical_ref'])
        reject_checking_corpus(materials,imported['checking_corpus_refs'])
        seed.need(reader.connection.execute('SELECT COUNT(*) FROM model_calls').fetchone()[0]==0
            and reader.connection.execute('SELECT COUNT(*) FROM tool_calls').fetchone()[0]==0,'FRESH_CORE_MUST_BE_ZERO_DISPATCH')
        seed.need(reader.connection.execute('SELECT COUNT(*) FROM runs').fetchone()[0]==0,'WORK_RUNS_ALREADY_EXIST')
    finally:reader.close()
    database=root/'core/state/research.sqlite3'
    facts={'schema':'ai4r-rsi-development-prepare-plan:1','id':value['id'],
        'input_sha256':seed.digest(seed.encoded(value)),'seed_receipt_sha256':value['seed_receipt']['sha256'],
        'core_sha256':seed.digest(seed.read(database,12001,256*1024*1024)),
        'public_refs':[pin for pin,_ in materials.values()], 'host_binding_ref':value['binding_ref'],'host_id':host_id,
        'source_pins':{Path(__file__).name:seed.digest(Path(__file__).read_bytes()),
            'rsi_development_run.py':seed.digest(Path(development.__file__).read_bytes()),
            'rsi_development_seed.py':seed.digest(Path(seed.__file__).read_bytes()),
            'composition':development.source_pins(),'intake':intake_source_pins()},
        'output':str(output),'public_closure_bound':closure_bound,'work_contexts':2,'model_calls':0,'qualification':False}
    return value,complete,original,packet,materials,binding,facts


async def capture(value,complete,original,packet,materials,binding):
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.library import LibraryService
    from jiuwenswarm.research.runner import Registry,CapsuleRunner
    from jiuwenswarm.research.checks import CheckRegistry
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research.operator_config import OperatorConfiguration
    from jiuwenswarm.research.uploads import UploadManager
    from jiuwenswarm.research.intake import extract_document,qualify_intake
    dest=complete['destination']; actor=value['principal']
    principal=Principal(actor['account_id'],frozenset({actor['workspace_id']}),frozenset({'upload','ingest','status'}),frozenset({'researcher'}))
    core=SQLiteRunStore(dest['core_root'],input_root=dest['input_root'],recover=False)
    try:
        operator=OperatorConfiguration.from_mapping(core.read_record(binding['configuration_ref']))
        seed.need(operator.snapshot()['cc']['router']['enabled'] is False,'DEVELOPMENT_ROUTING_FORBIDDEN')
        library=LibraryService(core)
        library.check_assets.bind_calibration_runtime(binding['protected_options']['calibration_runtime_ref'],
            **{key:binding[key] for key in ('configuration_ref','model_selection_profile_ref','deployment_ref')})
        verifier=core.read_record(original['work_capsule_refs']['verifier'],contract_id='capsule-declaration')
        entry=library.get(verifier['identity']['name'],verifier['identity']['version_label'])
        library.configure_verifier(core.read_record(entry['admission_ref'],contract_id='library-admission')['cc'])
        async def forbidden(*args,**kwargs):raise ValueError('METADATA_PREPARATION_HAS_NO_MODEL_OR_EXECUTION_AUTHORITY')
        runner=CapsuleRunner(core,Registry(),CheckRegistry(),model=forbidden,executor=None,check_assets=library.check_assets)
        uploads=UploadManager(core,dest['input_root'],extract_document,extraction_timeout_s=30,max_upload_bytes=4*1024*1024)
        documents=public_documents(materials,value['request_text'])
        uploaded=[await uploads.upload(principal,'docs',actor['workspace_id'],name,raw) for name,raw in sorted(documents.items())]
        options=binding['protected_options']
        intake=qualify_intake(core,principal,value['request_text'],[row['id'] for row in uploaded],workspace_id=actor['workspace_id'],
            **{key:options[key] for key in ('profile_ref','workspace_ref','input_directory_ref')})
        contexts=development.prepare_work_contexts(core=core,library=library,runner=runner,operator=operator,exact=binding,
            intake_ref=intake,action_id=value['id'],work_capsule_refs=original['work_capsule_refs'],account_id=actor['account_id'])
        for key in ('diagnosis_contract_ref','proposal_contract_ref'):
            contract=core.read_record(contexts[key],contract_id='subnode-execution-contract')
            runner._require_child_authority(contexts[key],contract);runner._require_check_assets(contract)
            seed.need(contract['bindings'][0]['role']=='work' and contract['subnode_limits']['model_calls']==1,'GENUINE_SINGLE_CALL_WORK_REQUIRED')
            core.reserve_uploads(contract['run_id'],[row['id'] for row in uploaded])
        content=core.read_record(intake,contract_id='qualified-intake')
        public=[pin for pin,_ in materials.values()]+[intake,content['request_ref'],*content['source_refs']]
        public=list({seed.encoded(pin):pin for pin in public}.values())
        seed.need(len(public)<=96,'PUBLIC_MODEL_CLOSURE_EXCEEDS_AUTHORIZATION_BOUND')
        seed.need(not core.connection.execute('SELECT 1 FROM model_calls LIMIT 1').fetchone()
            and not core.connection.execute('SELECT 1 FROM tool_calls LIMIT 1').fetchone(),'METADATA_EFFECT_DISPATCHED')
        return {'schema':'ai4r-rsi-development-preparation:1','id':value['id'],**contexts,'intake_ref':intake,
            'public_original_refs':public,'exact_binding_refs':binding,'host_binding_ref':value['binding_ref'],
            'host_id':core.read_record(value['binding_ref'])['host_id'],'work_capsule_refs':original['work_capsule_refs'],
            'parent_declaration_ref':packet['parent_declaration_ref'],'target_profile_ref':packet['target_profile_ref'],
            'visible_context_ref':packet['visible_context_ref'],'preparation_ref':packet['preparation_ref'],
            'model_calls':0,'qualification':False}
    finally:core.close()


def apply(input_path,reviewed):
    value,complete,original,packet,materials,binding,facts=snapshot(input_path)
    seed.need(seed.digest(seed.encoded(facts))==reviewed and snapshot(input_path)[-1]==facts,'EXACT_PREPARATION_PLAN_REVIEW_REQUIRED')
    output=Path(facts['output'])
    seed.exclusive(Path(input_path).with_name('claim.json'),{'schema':'ai4r-rsi-development-preparation-claim:1','plan_sha256':reviewed})
    # Metadata remains owned by the isolated caller. Root holds only the fixed
    # once marker and final receipt; no account/model service is opened.
    pid=os.fork()
    if pid==0:
        try:
            import signal
            def expired(signum,frame):raise TimeoutError('FINITE_METADATA_PREPARATION_DEADLINE')
            signal.signal(signal.SIGALRM,expired);signal.alarm(180)
            os.setgroups([]);os.setgid(12001);os.setuid(12001)
            result=asyncio.run(capture(value,complete,original,packet,materials,binding))
            development.exclusive(output,result);os._exit(0)
        except BaseException as error:
            import traceback
            development.exclusive(output.with_suffix('.failure.json'),{'exception_type':type(error).__name__,'diagnostic':traceback.format_exc()[-65536:]})
            os._exit(2)
    _,status=os.waitpid(pid,0)
    seed.need(os.waitstatus_to_exitcode(status)==0,'METADATA_PREPARATION_FAILED_RECONCILE_NO_REPLAY')
    raw=seed.read(output,12001)
    receipt={'schema':'ai4r-rsi-development-preparation-completion:1','id':value['id'],'plan_sha256':reviewed,
        'output':{'path':str(output),'sha256':seed.digest(raw)},'model_calls':0,'qualification':False}
    seed.exclusive(Path(input_path).with_name('complete.json'),receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('operation',choices=('plan','apply'));parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--review-sha256');args=parser.parse_args()
    seed.need(os.name=='posix' and os.geteuid()==0,'ROOT_PREPARATION_REQUIRED')
    result=snapshot(args.input)[-1] if args.operation=='plan' else apply(args.input,args.review_sha256)
    print(json.dumps(result,sort_keys=True))
