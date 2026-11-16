"""Pinned STRATA full-model driver and original/candidate comparison.

Only real process outputs satisfy this module. Parser tests use isolated files;
there is no fabricated output or alternate model service in the execution path.
"""
from __future__ import annotations
import array
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import struct
import sys

from .contracts import StageBlocked, StageFailure
from .strata_patch import PIN

HIDDEN, VOCAB, LAYERS, EXPERTS, EXPERT_FF = 2560, 248320, 48, 512, 640
EXPERT_BLOB = 3 * HIDDEN * EXPERT_FF * 18 // 64


def sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def _settings(ctx):
    settings={**ctx.options,**ctx.options.get('options',{})}
    tokens=settings.get('prompt_tokens')
    if not isinstance(tokens,list) or not tokens or any(type(token) is not int or not 0<=token<VOCAB for token in tokens):
        raise StageBlocked('prompt_tokens_missing','Pinned STRATA requires explicit valid prompt token IDs; configure options.prompt_tokens.',{'layer':'runtime_input','vocabulary':VOCAB})
    maximum=settings.get('max_new',1);context=settings.get('max_context',256)
    if type(maximum) is not int or type(context) is not int or not 1<=maximum<=context<2147483640 or len(tokens)+maximum>context:
        raise StageFailure('invalid_runtime_shape','Prompt plus generation must fit a positive max_context; invalid max_new/max_context')
    return {**settings,'prompt_tokens':tokens,'max_new':maximum,'max_context':context}


def inspect_model_pack(model_path, settings, source: Path):
    if not model_path:
        raise StageBlocked('model_missing','Supply the real canonical STRATA Q2_0 pack directory and its PLE GGUF.',{'layer':'model_loading'})
    pack=Path(model_path).expanduser().resolve()
    if not pack.is_dir():
        raise StageBlocked('model_pack_required','This pinned driver consumes the canonical full Q2_0 pack, not a GGUF filename or a renamed schema.',{'layer':'model_loading','required_tools':['tools/strata_pack.py','tools/pack_index.py']})
    required=['manifest.json','index.txt','dense.bin','embd.bin','experts.bin']
    missing=[name for name in required if not (pack/name).is_file()]
    if missing:raise StageBlocked('model_pack_incomplete','Real model pack files are missing.',{'layer':'model_loading','missing':missing,'path':str(pack)})
    try:manifest=json.loads((pack/'manifest.json').read_text())
    except (ValueError,UnicodeDecodeError) as error:raise StageFailure('model_contract_invalid','Invalid model manifest JSON') from error
    if manifest.get('format')!='strata-pack' or manifest.get('n_layers')!=LAYERS or manifest.get('n_experts_per_layer')!=EXPERTS:
        raise StageFailure('model_geometry_unsupported','Driver is pinned to the complete Flash-Next geometry: 48 layers and 512 experts')
    experts=manifest.get('experts',{})
    if experts.get('source_type')!='Q2_0' or experts.get('blob_bytes')!=EXPERT_BLOB or experts.get('form')!='S2':
        raise StageFailure('model_quantization_unsupported','Canonical planar Q2_0/S2 is required; other quantization is not a field rename')
    if (pack/'experts.bin').stat().st_size!=LAYERS*EXPERTS*EXPERT_BLOB:
        raise StageFailure('model_shape_mismatch','experts.bin does not contain every expert of every model layer')
    tensors=manifest.get('tensors',{})
    for name in ['token_embd.weight','output.weight']:
        if tensors.get(name,{}).get('shape')!=[HIDDEN,VOCAB]:
            raise StageFailure('model_shape_mismatch',f'{name} must have shape {[HIDDEN,VOCAB]}')
    files=manifest.get('files',{})
    for name in ['dense.bin','embd.bin','experts.bin']:
        if type(files.get(name)) is not int or files[name] <=0 or (pack/name).stat().st_size!=files[name]:
            raise StageFailure('model_size_mismatch',f'Manifest/file length mismatch: {name}')
    # Validate actual source spans and dimensions from weights.cpp's nineteen-field index.
    file_ids={0:'dense.bin',1:'embd.bin',2:'experts.bin'};rows=0;pool_bytes=0;declared_rows=0
    with (pack/'index.txt').open() as stream:
        for line in stream:
            if line.startswith('#'):
                header=re.match(r'# align (\d+) pool (\d+) tensors (\d+)',line)
                if header:pool_bytes=int(header[2]);declared_rows=int(header[3])
                continue
            fields=line.split()
            if len(fields)!=19:raise StageFailure('model_index_invalid','Expected nineteen fields per actual weights.cpp index row')
            try:values=list(map(int,fields[1:]))
            except ValueError as error:raise StageFailure('model_index_invalid','Index integer field is invalid') from error
            file_id,kind,offset,size,dst,dst_size,ne0,ne1=values[:8]
            tensor=tensors.get(fields[0]);shape=tensor.get('shape',[]) if isinstance(tensor,dict) else []
            if file_id not in file_ids or not 0<=kind<=3 or min(offset,dst)<0 or min(size,dst_size,ne0)<=0 or ne1<0:
                raise StageFailure('model_index_invalid',f'Invalid index contract: {fields[0]}')
            if offset+size>(pack/file_ids[file_id]).stat().st_size or dst+dst_size>pool_bytes or [shape[0] if shape else 0,shape[1] if len(shape)>1 else 0]!=[ne0,ne1]:
                raise StageFailure('model_index_bounds',f'Actual tensor span or shape does not fit: {fields[0]}')
            rows+=1
    if rows<=0 or rows!=declared_rows or rows!=len(tensors):raise StageFailure('model_index_incomplete','Index tensor count does not match the manifest/header')
    ple_value=settings.get('ple_gguf') or manifest.get('shard2_tensor',{}).get('path') or manifest.get('source',{}).get('shard2')
    if not ple_value:raise StageBlocked('ple_missing','Full model requires the PLE GGUF; --no-ple diagnostic ablation is not accepted.',{'layer':'model_loading'})
    ple=Path(ple_value).expanduser().resolve()
    if not ple.is_file():raise StageBlocked('ple_missing',f'PLE model shard is absent: {ple}',{'layer':'model_loading'})
    # Reuse the exact pinned source's real GGUF header reader. It reads local bytes only.
    reader_path=source/'tools/quantscope.py'
    spec=importlib.util.spec_from_file_location('factory_strata_quantscope',reader_path)
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    try:_,ple_tensors=reader.read_gguf(reader.Source(ple.name,ple.stat().st_size,path=str(ple)))
    except Exception as error:raise StageFailure('ple_contract_invalid',f'Cannot parse actual PLE GGUF: {error}') from error
    table=next((t for t in ple_tensors if t['name']=='per_layer_token_embd.weight'),None)
    if table is None or table['bytes']<=0 or table['elements']<=0:
        raise StageFailure('ple_contract_invalid','GGUF has no nonempty per_layer_token_embd.weight tensor')
    paths=[pack/name for name in required]+[ple]
    identities=[{'path':str(path),'size':path.stat().st_size,'sha256':sha256(path)} for path in paths]
    expected=manifest.get('source',{}).get('shard2_sha256')
    if expected and identities[-1]['sha256']!=expected:raise StageFailure('ple_identity_mismatch','PLE GGUF SHA differs from the model pack source')
    return {'pack_dir':str(pack),'ple_gguf':str(ple),'vocabulary':VOCAB,'layers':LAYERS,'files':identities,'index_rows':rows}


def inference_argv(binary: Path, model, settings, logits: Path):
    # generate.cpp:3431–3466 parses these flags directly; "generate" is NOT a parsed subcommand.
    return [str(binary),'--pack',model['pack_dir'],'--tokens',','.join(map(str,settings['prompt_tokens'])),
            '--max-new',str(settings['max_new']),'--max-context',str(settings['max_context']),
            '--greedy','--expert-cache','0','--ple-gguf',model['ple_gguf'],'--dump-logits',str(logits)]


def inspect_logits(path: Path, expected_rows=None, vocabulary=None):
    if not path.is_file() or path.stat().st_size<8:raise StageFailure('logits_missing','Engine did not write actual logits')
    with path.open('rb') as stream:
        vocab,rows=struct.unpack('<ii',stream.read(8))
        if not 0<vocab<=2_000_000 or not 0<rows<=2_000_000 or path.stat().st_size!=8+4*vocab*rows:
            raise StageFailure('logits_shape_invalid','Actual float32 logits length does not match its header')
        if (expected_rows is not None and rows!=expected_rows) or (vocabulary is not None and vocab!=vocabulary):
            raise StageFailure('logits_shape_mismatch','Logits shape does not match model vocabulary and executed positions')
        while data:=stream.read(4*65536):
            values=array.array('f');values.frombytes(data)
            if sys.byteorder!='little':values.byteswap()
            if any(not math.isfinite(value) for value in values):raise StageFailure('logits_nonfinite','Engine logits contain NaN or infinity')
    return {'path':str(path),'sha256':sha256(path),'vocabulary':vocab,'rows':rows,'dtype':'float32-le','bytes':path.stat().st_size}


def role_backend(ctx, role):
    """The original reference is not required to use the candidate backend."""
    if role == 'original':
        backend = ctx.options.get('options', {}).get('reference_backend',
                    ctx.options.get('reference_backend', 'cuda'))
        if backend != 'cuda':
            raise StageBlocked('original_backend_unavailable',
                'The pinned original full-model reference supports the reviewed CUDA driver.',
                {'layer': 'original_compile', 'reference_backend': backend})
        return backend
    if role != 'candidate':
        raise StageFailure('invalid_inference_role', 'Expected original or candidate inference role')
    return ctx.options.get('target_backend', 'ascend')


def _run_inference(ctx,inputs,binary_key,output_key):
    binary_manifest=inputs[binary_key].read_json();backend=binary_manifest.get('backend')
    role = 'original' if output_key == 'baseline' else 'candidate'
    expected_backend = role_backend(ctx, role)
    if backend != expected_backend:
        raise StageFailure('backend_mismatch', f'Requested {role} backend and compiled engine backend differ; fallback is forbidden')
    if binary_manifest.get('role') != role or binary_manifest.get('full_model_binary') is not True:
        raise StageFailure('binary_role_mismatch', 'Inference requires the role-specific full model engine artifact')
    integration = None
    if role == 'candidate':
        from .generated_candidate import validate_generated_candidate
        manifest_path = binary_manifest.get('implementation_manifest_path')
        if not isinstance(manifest_path, str) or not Path(manifest_path).is_file() or sha256(Path(manifest_path)) != binary_manifest.get('implementation_manifest_sha256'):
            raise StageFailure('candidate_integration_missing', 'Candidate inference requires the actual generated-source integration receipt')
        validate_generated_candidate(Path(manifest_path))
        integration = json.loads(Path(manifest_path).read_text())
        if (integration['source_dir'] != binary_manifest.get('source_dir') or
            integration['generated_manifest_sha256'] != binary_manifest.get('generated_manifest_sha256') or
            integration['files'] != binary_manifest.get('integrated_files') or
            integration['algorithms'] != binary_manifest.get('algorithms')):
            raise StageFailure('candidate_integration_changed', 'Compiled candidate is not bound to the checked generated computation bytes')
    if backend=='ascend' and not binary_manifest.get('full_native_model'):
        raise StageBlocked('native_backend_incomplete','No verified full native Ascend STRATA binary is available.',{'layer':'end_to_end_inference'})
    if backend not in {'cuda','ascend'}:raise StageBlocked('unsupported_full_backend','Pinned driver has no full CPU inference engine.',{'layer':'end_to_end_inference'})
    environment=inputs['environment'].read_json()
    if not environment.get('devices',{}).get(backend):raise StageBlocked('target_device_missing',f'No native {backend} device is recorded.',{'layer':'device_loading'})
    source=Path(binary_manifest['source_dir']).resolve(strict=True)
    if binary_manifest.get('commit_sha')!=PIN:raise StageFailure('binary_source_mismatch','Inference binary is not built from the reviewed STRATA commit')
    binary=Path(binary_manifest['path']).resolve(strict=True)
    if binary_manifest.get('sha256')!=sha256(binary):raise StageFailure('binary_changed','Full engine binary changed since compilation')
    settings=_settings(ctx)
    model=inspect_model_pack(ctx.options.get('model_path'),settings,source)
    geometry=ctx.run_command([str(binary),'--geometry'],cwd=source,timeout=30)
    if geometry['stdout'].strip()!='flash_next':raise StageFailure('binary_geometry_mismatch','Compiled engine is not the inspected full Flash-Next geometry')
    version=ctx.run_command([str(binary),'--version'],cwd=source,timeout=30)
    logits=ctx.workspace/'logits.f32'
    command=inference_argv(binary,model,settings,logits)
    execution_env={'STRATA_EXPERT_BACKEND':'ascend' if backend=='ascend' else 'cpu'}
    calls_path=ctx.workspace/'generated-core-calls.json'
    if integration is not None:
        if calls_path.exists():
            raise StageFailure('generated_execution_receipt_stale','Execution receipt path must be fresh for this actual model process')
        execution_env['STRATA_FACTORY_TRACE_PATH']=str(calls_path)
    result=ctx.run_command(command,cwd=source,timeout=int(settings.get('inference_timeout',1800)),env=execution_env)
    generated_execution=None
    if integration is not None:
        from .generated_candidate import inspect_generated_calls
        generated_execution={'receipt':inspect_generated_calls(calls_path,integration['algorithms']),
            'path':str(calls_path),'sha256':sha256(calls_path),
            'generated_manifest_sha256':integration['generated_manifest_sha256'],
            'execution_strategy':integration['execution_strategy']}
    # Read the complete process artifact, not the Context's bounded preview.
    stdout=Path(result['stdout_path']).read_text()
    match=re.search(r'^output\s*:\s*([\d\s]+)$',stdout,re.MULTILINE)
    if not match:raise StageFailure('generated_tokens_missing','Pinned engine did not emit its real output token IDs')
    tokens=[int(token) for token in match[1].split()]
    if len(tokens)!=settings['max_new'] or any(not 0<=token<VOCAB for token in tokens):raise StageFailure('generated_tokens_invalid','Actual generated token count or token IDs are invalid')
    tensor=inspect_logits(logits,len(settings['prompt_tokens'])-1+settings['max_new'],VOCAB)
    return {output_key:ctx.write_json(f'{output_key}.json',{
        'schema':'factory.strata.inference.v1','backend':backend,'role':role,'binary':binary_manifest,'binary_manifest_sha256':inputs[binary_key].sha256,
        'model':model,'settings':{'prompt_tokens':settings['prompt_tokens'],'max_new':settings['max_new'],'max_context':settings['max_context'],'sampling':'greedy','expert_cache':0},
        'generated_tokens':tokens,'logits':tensor,'command':command,'stdout_path':result['stdout_path'],'stderr_path':result['stderr_path'],'engine_version':version['stdout'].strip(),
        'layers':{'device_loading':'passed','operator_execution':'passed','model_inference':'passed','original_comparison':'not_run'},
        'ascend_validated':backend=='ascend' and role=='candidate',
        'execution_strategy':binary_manifest.get('execution_strategy',backend),
        'generated_core_execution':generated_execution})}


def run_candidate_inference(ctx,inputs):return _run_inference(ctx,inputs,'binary','inference')
def run_baseline_inference(ctx,inputs):return _run_inference(ctx,inputs,'baseline_binary','baseline')


def build_baseline_engine(ctx,inputs):
    source=inputs['source'].read_json();environment=inputs['environment'].read_json()
    backend=role_backend(ctx, 'original')
    if not environment.get('sdk',{}).get('nvcc'):raise StageBlocked('cuda_sdk_missing','Original full engine requires the actual CUDA SDK.',{'layer':'original_compile'})
    checkout=Path(source['source_dir']).resolve(strict=True)
    if source.get('commit_sha')!=PIN:raise StageFailure('source_pin_mismatch','Unreviewed STRATA source commit')
    status=ctx.run_command(['git','status','--porcelain','--untracked-files=no'],cwd=checkout)
    if status['stdout'].strip():raise StageFailure('baseline_modified','Original baseline source contains tracked modifications')
    cmake=ctx.options.get('cmake') or shutil.which('cmake') or 'cmake';build=ctx.workspace/'original-build'
    command=[cmake,'--preset','cuda-compile','-B',str(build)]
    if ctx.options.get('ninja'):command.append(f'-DCMAKE_MAKE_PROGRAM={ctx.options["ninja"]}')
    arch=ctx.options.get('options',{}).get('cuda_architectures')
    if arch:command.append(f'-DCMAKE_CUDA_ARCHITECTURES={arch}')
    ctx.run_command(command,cwd=checkout,timeout=300)
    ctx.run_command([cmake,'--build',str(build),'--target','strata','--parallel','2'],cwd=checkout,timeout=3600)
    binary=build/'strata'
    if not binary.is_file():raise StageFailure('binary_missing','Original CMake build did not produce its declared full engine')
    return {'baseline_binary':ctx.write_json('original-engine.json',{'schema':'factory.strata.binary.v1','path':str(binary),'sha256':sha256(binary),'source_dir':str(checkout),'commit_sha':PIN,'backend':backend,'role':'original','full_model_binary':True})}


def _model_identity(model):
    """Compare exact weight/configuration bytes, not machine-local mount paths."""
    files = model.get('files')
    if not isinstance(files, list) or len(files) != 6:
        raise StageFailure('model_identity_missing', 'Comparison requires every canonical pack file and PLE fingerprint')
    roles = ['manifest.json', 'index.txt', 'dense.bin', 'embd.bin', 'experts.bin', 'ple.gguf']
    identities = []
    for role, record in zip(roles, files):
        if not isinstance(record.get('sha256'), str) or not re.fullmatch(r'[a-f0-9]{64}', record['sha256']) or type(record.get('size')) is not int or record['size'] <= 0:
            raise StageFailure('model_identity_invalid', f'Invalid actual model fingerprint: {role}')
        identities.append({'role': role, 'sha256': record['sha256'], 'size': record['size']})
    return {'vocabulary': model.get('vocabulary'), 'layers': model.get('layers'),
            'index_rows': model.get('index_rows'), 'files': identities}


def compare_model_outputs(ctx,inputs):
    candidate=inputs['inference'].read_json();baseline=inputs['baseline'].read_json()
    if candidate.get('schema')!='factory.strata.inference.v1' or baseline.get('schema')!=candidate['schema']:
        raise StageFailure('inference_contract_invalid','Comparison requires real full-engine output artifacts')
    if candidate.get('role') != 'candidate' or baseline.get('role') != 'original':
        raise StageFailure('inference_role_mismatch', 'Comparison requires distinct candidate and original inference roles')
    if candidate['settings']!=baseline['settings'] or _model_identity(candidate['model'])!=_model_identity(baseline['model']):
        raise StageFailure('comparison_input_mismatch','Original and candidate must consume identical model bytes and prompt/settings')
    if candidate['generated_tokens']!=baseline['generated_tokens']:
        raise StageFailure('token_mismatch','Original and candidate generated different token IDs',{'original':baseline['generated_tokens'],'candidate':candidate['generated_tokens']})
    cpath=Path(candidate['logits']['path']);bpath=Path(baseline['logits']['path'])
    for path,record in [(cpath,candidate['logits']),(bpath,baseline['logits'])]:
        if sha256(path)!=record['sha256']:raise StageFailure('inference_output_changed','Actual logits changed before comparison')
    cshape=inspect_logits(cpath);bshape=inspect_logits(bpath)
    if (cshape['rows'],cshape['vocabulary'])!=(bshape['rows'],bshape['vocabulary']):raise StageFailure('comparison_shape_mismatch','Original and candidate logits shapes differ')
    options=ctx.options.get('options',{});atol=float(options.get('logits_atol',1e-5));rtol=float(options.get('logits_rtol',1e-4))
    if not math.isfinite(atol) or not math.isfinite(rtol) or min(atol,rtol)<0:raise StageFailure('invalid_tolerance','Logit tolerances must be finite and nonnegative')
    count=0;failed=0;maximum=0.
    with cpath.open('rb') as c,bpath.open('rb') as b:
        c.seek(8);b.seek(8)
        while raw:=c.read(4*65536):
            cv=array.array('f');bv=array.array('f');cv.frombytes(raw);bv.frombytes(b.read(len(raw)))
            if len(cv)!=len(bv):raise StageFailure('comparison_shape_mismatch','Logits changed or truncated during comparison')
            if sys.byteorder!='little':cv.byteswap();bv.byteswap()
            for actual,reference in zip(cv,bv):
                error=abs(actual-reference);maximum=max(maximum,error);count+=1
                if error>atol+rtol*abs(reference):failed+=1
    if count!=cshape['rows']*cshape['vocabulary']:raise StageFailure('comparison_shape_mismatch','Logits count changed during comparison')
    if failed:raise StageFailure('logits_mismatch','Actual original/candidate model logits exceed tolerance',{'mismatched_values':failed,'compared_values':count,'max_abs_error':maximum,'atol':atol,'rtol':rtol})
    return {'comparison':ctx.write_json('model-comparison.json',{'schema':'factory.strata.comparison.v1','status':'passed','backend':candidate['backend'],'model_files':candidate['model']['files'],'prompt_settings':candidate['settings'],'generated_tokens':candidate['generated_tokens'],'logits_compared':count,'max_abs_error':maximum,'atol':atol,'rtol':rtol,'candidate_manifest_sha256':inputs['inference'].sha256,'baseline_manifest_sha256':inputs['baseline'].sha256,'candidate_backend':candidate['backend'],'reference_backend':baseline['backend'],
        'ascend_validated':candidate['backend']=='ascend' and candidate.get('ascend_validated') is True,
        'reference_manifest_sha256':inputs['baseline'].sha256})}
