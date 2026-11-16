"""Real STRATA implementation/build stages; no simulated inference results."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
from .contracts import StageFailure, StageBlocked
from .strata_patch import PIN, apply_port


def _manifest(artifact):
    value=artifact.read_json()
    if not isinstance(value,dict):raise StageFailure('contract_invalid','STRATA artifact must contain a JSON object')
    return value


def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def implement_strata(ctx,inputs):
    source=_manifest(inputs['source'])
    source_dir=Path(source['source_dir']).resolve(strict=True)
    analysis=_manifest(inputs['analysis'])
    if analysis.get('commit_sha') != source.get('commit_sha') or Path(analysis.get('source_dir','')).resolve() != source_dir:
        raise StageFailure('analysis_source_mismatch','Source analysis must describe this exact acquired checkout and commit')
    for item in analysis.get('files',[]):
        path=Path(item['absolute_path']).resolve(strict=True)
        if not path.is_relative_to(source_dir) or _sha(path)!=item['sha256']:
            raise StageFailure('analysis_source_changed',f'Analyzed source changed before construction: {path}')
    if not analysis.get('files') or not analysis.get('mechanism_evidence'):
        raise StageFailure('analysis_incomplete','Construction requires inspected source evidence, not an empty schema')
    mechanism_files={
        'model_loading':['src/core/weights.cpp','src/core/expert_source.cpp'],
        'expert_routing':['src/kernels/cuda/router_top10.cu'],
        'expert_cache':['include/strata/core/expert_cache.hpp'],
        'cpu_gpu_partition':['src/kernels/cpu/pool.cpp','cmake/strata_gpu_engine.cmake'],
        'model_forward_output':['src/program/generate.cpp','include/strata/core/geometry.hpp'],
        'ported_arithmetic':['src/kernels/cpu/expert.cpp','include/strata/kernels/cpu/expert.hpp'],
    }
    consumed_source=[]
    for mechanism,paths in mechanism_files.items():
        for relative in paths:
            path=(source_dir/relative).resolve(strict=True)
            if not path.is_relative_to(source_dir):raise StageFailure('source_path_escape',relative)
            consumed_source.append({'mechanism':mechanism,'path':relative,'sha256':_sha(path),'bytes':path.stat().st_size})
    if source.get('commit_sha')!=PIN:
        raise StageFailure('unsupported_source_revision',f'This reviewed patch requires STRATA {PIN}, received {source.get("commit_sha")}')
    checkout=ctx.workspace/'strata'
    ctx.run_command(['git','clone','--local','--no-hardlinks',str(source_dir),str(checkout)],timeout=180)
    ctx.run_command(['git','checkout','--detach',PIN],cwd=checkout)
    actual=ctx.run_command(['git','rev-parse','HEAD'],cwd=checkout)['stdout'].strip()
    if actual!=PIN:raise StageFailure('source_pin_mismatch',f'{actual} != {PIN}')
    patch=apply_port(checkout)
    diff=ctx.run_command(['git','diff','--','src/kernels/cpu/pool.cpp','cmake/backends/cpu.cmake'],cwd=checkout)
    return {'implementation':ctx.write_json('implementation.json',{
        'schema':'factory.strata.implementation.v1','source_dir':str(checkout),'commit_sha':actual,
        'baseline_manifest':inputs['source'].path,'baseline_manifest_sha256':inputs['source'].sha256,
        'patch':patch,'diff_stdout_path':diff['stdout_path'],
        'analysis_manifest':inputs['analysis'].path,'analysis_manifest_sha256':inputs['analysis'].sha256,
        'consumed_source_modules':consumed_source,
        'target_requirements':{'target_backend':ctx.options.get('target_backend','ascend'),'native_device_required':True,'full_model_required':True,'cpu_fallback_permitted':False,'model_path':ctx.options.get('model_path')},
        'correspondence':[
            {'original':'src/kernels/cpu/expert.cpp:s2_expert_scalar and planar Q2_0 constants','candidate':'include/strata/kernels/ascend/expert_adapter.hpp','verification':'strata_ascend_adapter_test compares 10240 values with unchanged upstream scalar arithmetic; CPU data adapter only'},
            {'original':'src/kernels/cpu/pool.cpp:run/run_split/run_split_multi/run_split_multi_native','candidate':'same functions dispatch opt-in canonical jobs to src/kernels/ascend/expert.cpp','verification':'actual ExpertPool rejects requested unavailable Ascend backend; unsupported native formats fail explicitly'},
            {'original':'canonical expert gate/up projection, SiLU(gate)*up, Q8 intermediate boundary, down projection','candidate':'CANN aclnnMatmul + aclnnSilu + aclnnMul with original host Q8 boundary','verification':'CANN compile/device/operator validation remains blocked until actual SDK/device are available'},
            {'original':'src/core/weights.cpp, expert_source.cpp, router_top10.cu, expert_cache.hpp, program/generate.cpp','candidate':'original loader/router/cache/full forward reused unmodified; full Ascend migration incomplete','verification':'not passed as full-model reproduction; missing native operations enumerated below'},
        ],
        'layers':{'source_implementation':'partial','host_compilation':'not_run','native_compilation':'not_run','device_loading':'not_run','operator_execution':'not_run','model_inference':'not_run','original_comparison':'not_run'},
        'model_loader_reused':'src/core/weights.cpp and src/core/expert_source.cpp',
        'modified_computation':'ExpertPool canonical Q2_0 gate/up/down projections and SwiGLU; both Q8 activation boundaries preserved',
        'native_limits':patch['unimplemented_full_model_operations']})}


def _implementation(artifact):
    value=_manifest(artifact);checkout=Path(value['source_dir']).resolve(strict=True)
    for file in value['patch']['files']:
        path=(checkout/file['path']).resolve(strict=True)
        if not path.is_relative_to(checkout) or _sha(path)!=file['sha256']:
            raise StageFailure('implementation_changed',f'Implementation source changed: {path}')
    return value,checkout


def build_strata_components(ctx,inputs):
    implementation,checkout=_implementation(inputs['implementation'])
    cmake=ctx.options.get('cmake') or shutil.which('cmake') or 'cmake'
    ninja=ctx.options.get('ninja') or shutil.which('ninja')
    ctx.run_command([cmake,'--version'],cwd=checkout)
    build=ctx.workspace/'build'
    command=[cmake,'-S',str(checkout),'-B',str(build),'-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DSTRATA_BUILD_TESTS=ON','-DSTRATA_NATIVE_EXPERTS=OFF']
    if ninja:command.append(f'-DCMAKE_MAKE_PROGRAM={ninja}')
    ctx.run_command(command,cwd=checkout,timeout=180)
    targets=['strata-plan','strata_ascend_adapter_test','pool_stress']
    ctx.run_command([cmake,'--build',str(build),'--target',*targets,'--parallel','2'],cwd=checkout,timeout=600)
    binaries={name:str((build/name).resolve(strict=True)) for name in targets}
    return {'build':ctx.write_json('component-build.json',{
        'schema':'factory.strata.component-build.v1','source_dir':str(checkout),'build_dir':str(build),'commit_sha':implementation['commit_sha'],
        'implementation_manifest':inputs['implementation'].path,'implementation_manifest_sha256':inputs['implementation'].sha256,
        'binaries':binaries,'binary_sha256':{name:_sha(path) for name,path in binaries.items()},
        'scope':'CPU components including actual ExpertPool and portable Ascend data adapter; not a full-model inference binary',
        'layers':{'source_implementation':'partial','host_compilation':'passed','native_compilation':'not_run','device_loading':'not_run','operator_execution':'not_run','model_inference':'not_run','original_comparison':'not_run'}})}


def verify_strata_components(ctx,inputs):
    build=_manifest(inputs['build']);results=[]
    for name,args in [('strata_ascend_adapter_test',[]),('pool_stress',['3']),('strata-plan',[])]:
        path=Path(build['binaries'][name]).resolve(strict=True)
        if _sha(path)!=build['binary_sha256'][name]:raise StageFailure('binary_changed',str(path))
        result=ctx.run_command([str(path),*args],cwd=Path(build['source_dir']),timeout=60)
        if name=='strata_ascend_adapter_test':
            try:parity=json.loads(result['stdout'].strip())
            except ValueError as error:raise StageFailure('invalid_test_output','No actual numerical parity result') from error
            if parity.get('outputs_compared',0)<10240 or parity.get('max_abs_error',1)>1e-5:
                raise StageFailure('numerical_mismatch','STRATA planar expert transformation failed',parity)
            results.append(parity)
        else:results.append({'check':name,'stdout_path':result['stdout_path'],'exit_code':result['exit_code']})
    return {'verification':ctx.write_json('component-verification.json',{
        'schema':'factory.strata.component-verification.v1','build_manifest':inputs['build'].path,'build_manifest_sha256':inputs['build'].sha256,
        'checks':results,'status':'passed','scope':'Host numerical transformation and actual CPU ExpertPool components only',
        'native_device_validated':False,'full_inference_validated':False,'original_model_comparison_validated':False})}


def build_strata_native(ctx,inputs):
    implementation,checkout=_implementation(inputs['implementation'])
    cann=Path(ctx.options.get('ascend_home') or os.environ.get('ASCEND_HOME_PATH','/usr/local/Ascend/ascend-toolkit/latest'))
    report={'source_implementation':'partial','native_compilation':'blocked','device_loading':'not_run','operator_execution':'not_run','model_inference':'not_run','original_comparison':'not_run',
        'missing_operations':implementation['native_limits'],'sdk_path':str(cann),'sdk_headers_available':(cann/'include/acl/acl.h').is_file(),'model_path':ctx.options.get('model_path')}
    if not report['sdk_headers_available']:
        raise StageBlocked('ascend_sdk_missing','CANN headers/libraries are absent; native compilation, device loading and model inference cannot pass',report)
    cmake=ctx.options.get('cmake') or shutil.which('cmake') or 'cmake'
    build=ctx.workspace/'native-expert-build'
    command=[cmake,'-S',str(checkout),'-B',str(build),'-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DSTRATA_BUILD_TESTS=ON','-DSTRATA_NATIVE_EXPERTS=OFF','-DSTRATA_ENABLE_ASCEND_EXPERTS=ON',f'-DASCEND_HOME_PATH={cann}']
    if ctx.options.get('ninja'):command.append(f'-DCMAKE_MAKE_PROGRAM={ctx.options["ninja"]}')
    ctx.run_command(command,cwd=checkout,timeout=180)
    ctx.run_command([cmake,'--build',str(build),'--target','strata_kernels_cpu','--parallel','2'],cwd=checkout,timeout=600)
    report['native_compilation']='passed'
    raise StageBlocked('ascend_full_model_unimplemented','Native expert compilation does not implement the remaining full-model kernels; a complete Ascend STRATA inference binary is unavailable',report)
