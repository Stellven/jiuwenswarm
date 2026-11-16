"""Integrate generated algorithm bytes into a pinned full-engine candidate.

The CUDA option deliberately transfers selected tensors to generated host cores.
It is a separate, explicit backend strategy, never an Ascend implementation.
Native Ascend remains blocked until the entire model computation graph exists.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil

from .contracts import StageFailure, json_object
from .strata_patch import PIN

ALGORITHMS = ('router', 'swiglu', 'moe_combine')
MISSING_NATIVE = [
    'native embedding and dense projection kernels',
    'native router, expert projections, SwiGLU and aggregation execution',
    'QSA/GDN attention, recurrent state and KV cache on the native device',
    'native memory transfers, graph scheduling, sampling and output token loop',
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


BRIDGE_HEADER = r'''#pragma once
#include <cstddef>
#include <cstdint>
namespace strata_factory {
enum class Operation { Router, SwiGLU, Combine };
struct Work {
 Operation operation; int tokens=0,experts=0,k=0,n=0; int64_t width=0;
 const float *a=nullptr,*b=nullptr,*c=nullptr;
 float* y=nullptr; int* ids=nullptr;
 std::size_t a_count=0,b_count=0,c_count=0,y_count=0,ids_count=0;
};
struct HostBuffers {float *a,*b,*c,*y;int* ids;};
void compute_host(const Work&,const HostBuffers&);
void enqueue(const Work&,void*);
void prepare_cuda_pool(std::size_t element_capacity,std::size_t slots);
void route_cuda(const float*,int,int,int,int*,float*,void*);
void swiglu_cuda(const float*,const float*,float*,int,void*);
void combine_cuda(const float*,const float*,const float*,float*,int64_t,int64_t,void*);
}
'''

BRIDGE_SOURCE = r'''#include "generated_bridge.h"
#include "strata_core.h"
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <stdexcept>
#include <vector>
namespace strata_factory {
namespace {
std::atomic<unsigned long long> router_calls{0},swiglu_calls{0},combine_calls{0};
struct Receipt {
 ~Receipt() {
  const char* path=std::getenv("STRATA_FACTORY_TRACE_PATH");if(!path||!*path)return;
  FILE* file=std::fopen(path,"w");if(!file)return;
  std::fprintf(file,"{\"schema\":\"factory.generated_core.calls.v1\",\"execution_strategy\":\"cuda+host_generated_cores\",\"calls\":{\"router\":%llu,\"swiglu\":%llu,\"moe_combine\":%llu}}\n",router_calls.load(),swiglu_calls.load(),combine_calls.load());
  std::fclose(file);
 }
} receipt;
int dimension(int64_t value) {
 if(value<=0||value>std::numeric_limits<int>::max())throw std::runtime_error("generated bridge invalid dimension");
 return int(value);
}
}
void compute_host(const Work& work,const HostBuffers& host) {
 switch(work.operation) {
#if defined(STRATA_FACTORY_GENERATED_ROUTER)
 case Operation::Router:
  for(int t=0;t<work.tokens;++t){
   const float* row=host.a+std::size_t(t)*work.experts;
   auto result=strata_core::route(std::vector<float>(row,row+work.experts),work.k);
   for(int i=0;i<work.k;++i){host.ids[std::size_t(t)*work.k+i]=result.ids.at(i);host.y[std::size_t(t)*work.k+i]=result.weights.at(i);}
  }
  ++router_calls;return;
#endif
#if defined(STRATA_FACTORY_GENERATED_SWIGLU)
 case Operation::SwiGLU:
  strata_core::swiglu(host.a,host.b,host.y,work.n);++swiglu_calls;return;
#endif
#if defined(STRATA_FACTORY_GENERATED_MOE_COMBINE)
 case Operation::Combine:
  strata_core::moe_combine(host.a,host.b,work.c?host.c:nullptr,host.y,dimension(work.width),work.k,work.c?1:0);++combine_calls;return;
#endif
 default:throw std::runtime_error("algorithm not compiled into generated bridge");
 }
}
#if defined(STRATA_FACTORY_GENERATED_ROUTER)
void route_cuda(const float* logits,int tokens,int experts,int k,int* ids,float* weights,void* stream) {
 if(tokens<=0||experts<=0||k<=0)return;
 if(k>experts||k>64)throw std::runtime_error("generated router invalid top-k");
 Work job;job.operation=Operation::Router;job.tokens=tokens;job.experts=experts;job.k=k;
 job.a=logits;job.y=weights;job.ids=ids;job.a_count=std::size_t(tokens)*experts;
 job.y_count=job.ids_count=std::size_t(tokens)*k;enqueue(job,stream);
}
#endif
#if defined(STRATA_FACTORY_GENERATED_SWIGLU)
void swiglu_cuda(const float* gate,const float* up,float* out,int n,void* stream) {
 if(n<=0)return;Work job;job.operation=Operation::SwiGLU;job.n=n;
 job.a=gate;job.b=up;job.y=out;job.a_count=job.b_count=job.y_count=n;enqueue(job,stream);
}
#endif
#if defined(STRATA_FACTORY_GENERATED_MOE_COMBINE)
void combine_cuda(const float* parts,const float* weights,const float* shared,float* out,int64_t width,int64_t experts,void* stream) {
 int n=dimension(width),k=dimension(experts);if(k>64)throw std::runtime_error("generated combine invalid top-k");
 Work job;job.operation=Operation::Combine;job.width=n;job.k=k;job.a=parts;job.b=weights;job.c=shared;job.y=out;
 job.a_count=std::size_t(n)*k;job.b_count=k;job.c_count=shared?n:0;job.y_count=n;enqueue(job,stream);
}
#endif
}
'''

CUDA_TRANSPORT = r'''#include "generated_bridge.h"
#include <cuda_runtime.h>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>
// Single model process; the pinned generation loop serializes replay of a graph.
// Pinned buffers persist until process exit, outliving every captured host node.
// The callback calls generated CPU math only. It never calls any CUDA API.
namespace strata_factory {
namespace {
void checked(cudaError_t status){if(status!=cudaSuccess)throw std::runtime_error(std::string("generated CUDA transport: ")+cudaGetErrorString(status));}
struct Cached {
 Work work;HostBuffers host{};std::atomic_flag computing=ATOMIC_FLAG_INIT;
};
using Key=std::tuple<std::uintptr_t,unsigned long long,int,std::uintptr_t,std::uintptr_t,std::uintptr_t,std::uintptr_t,std::uintptr_t,int,int,int,int,int64_t>;
struct State {
 std::mutex mutex;float* storage=nullptr;std::size_t capacity=0,slots=0,used=0;
 std::map<Key,std::unique_ptr<Cached>> jobs;
};
State& state(){static auto* owned=new State;return *owned;}
void CUDART_CB calculate(void* opaque){
 auto& job=*static_cast<Cached*>(opaque);
 if(job.computing.test_and_set()){std::fputs("generated bridge refuses concurrent replay using the same staging context\n",stderr);std::abort();}
 try{compute_host(job.work,job.host);}
 catch(const std::exception& error){std::fprintf(stderr,"generated host computation failed: %s\n",error.what());std::abort();}
 job.computing.clear();
}
}
void prepare_cuda_pool(std::size_t elements,std::size_t slots){
 if(!elements||!slots||elements>16777216||slots>65536)throw std::runtime_error("generated pinned pool invalid geometry");
 auto& owner=state();std::lock_guard<std::mutex> lock(owner.mutex);
 if(owner.storage){if(elements>owner.capacity||slots>owner.slots)throw std::runtime_error("generated pinned pool geometry changed after preparation");return;}
 checked(cudaHostAlloc(reinterpret_cast<void**>(&owner.storage),elements*slots*sizeof(float),cudaHostAllocPortable));
 owner.capacity=elements;owner.slots=slots;
}
void enqueue(const Work& work,void* stream){
 auto& owner=state();cudaStream_t cs=static_cast<cudaStream_t>(stream);
 cudaStreamCaptureStatus status;unsigned long long capture=0;
 checked(cudaStreamGetCaptureInfo(cs,&status,&capture));
 std::lock_guard<std::mutex> lock(owner.mutex);
 // The cache key also distinguishes separate captures on recycled stream handles.
 Key key{reinterpret_cast<std::uintptr_t>(stream),capture,int(work.operation),
  reinterpret_cast<std::uintptr_t>(work.a),reinterpret_cast<std::uintptr_t>(work.b),reinterpret_cast<std::uintptr_t>(work.c),
  reinterpret_cast<std::uintptr_t>(work.y),reinterpret_cast<std::uintptr_t>(work.ids),work.tokens,work.experts,work.k,work.n,work.width};
 auto found=owner.jobs.find(key);
 if(found==owner.jobs.end()){
  const auto needed=work.a_count+work.b_count+work.c_count+work.y_count+work.ids_count;
  if(!owner.storage||needed>owner.capacity||owner.used>=owner.slots)
   throw std::runtime_error("generated staging missing: prepare pinned geometry buffers before capture; unknown shape/capture capacity is refused");
  auto job=std::make_unique<Cached>();job->work=work;
  float* memory=owner.storage+owner.used++*owner.capacity;
  job->host.a=memory;memory+=work.a_count;job->host.b=memory;memory+=work.b_count;
  job->host.c=memory;memory+=work.c_count;job->host.y=memory;memory+=work.y_count;
  job->host.ids=reinterpret_cast<int*>(memory);
  found=owner.jobs.emplace(key,std::move(job)).first;
 }
 auto& job=*found->second;
 if(work.a_count)checked(cudaMemcpyAsync(job.host.a,work.a,work.a_count*sizeof(float),cudaMemcpyDeviceToHost,cs));
 if(work.b_count)checked(cudaMemcpyAsync(job.host.b,work.b,work.b_count*sizeof(float),cudaMemcpyDeviceToHost,cs));
 if(work.c_count)checked(cudaMemcpyAsync(job.host.c,work.c,work.c_count*sizeof(float),cudaMemcpyDeviceToHost,cs));
 checked(cudaLaunchHostFunc(cs,calculate,&job));
 if(work.y_count)checked(cudaMemcpyAsync(work.y,job.host.y,work.y_count*sizeof(float),cudaMemcpyHostToDevice,cs));
 if(work.ids_count)checked(cudaMemcpyAsync(work.ids,job.host.ids,work.ids_count*sizeof(int),cudaMemcpyHostToDevice,cs));
 // Capturing never synchronizes. Direct calls preserve the original synchronous
 // null-stream contract; actual model graph replay synchronization stays upstream.
 if(status==cudaStreamCaptureStatusNone && !stream)checked(cudaStreamSynchronize(cs));
}
}
'''

HOST_TRANSPORT_TEST = r'''// Isolated host transport verifies the identical callback math, not CUDA/device execution.
#include "generated_bridge.h"
#include <cmath>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>
namespace strata_factory {
void prepare_cuda_pool(std::size_t,std::size_t){}
void enqueue(const Work& job,void*){
 std::vector<float>a(job.a_count),b(job.b_count),c(job.c_count),y(job.y_count);std::vector<int>ids(job.ids_count);
 if(job.a_count)std::memcpy(a.data(),job.a,job.a_count*sizeof(float));
 if(job.b_count)std::memcpy(b.data(),job.b,job.b_count*sizeof(float));
 if(job.c_count)std::memcpy(c.data(),job.c,job.c_count*sizeof(float));
 compute_host(job,HostBuffers{a.data(),b.data(),c.data(),y.data(),ids.data()});
 if(job.y_count)std::memcpy(job.y,y.data(),job.y_count*sizeof(float));
 if(job.ids_count)std::memcpy(job.ids,ids.data(),job.ids_count*sizeof(int));
}
}
void close(float a,float b){if(std::fabs(a-b)>1e-5f)throw std::runtime_error("bridge arithmetic mismatch");}
int main(){
#if defined(STRATA_FACTORY_GENERATED_ROUTER)
 float logits[]={0,1,1,-1},weights[2];int ids[2];strata_factory::route_cuda(logits,1,4,2,ids,weights,nullptr);
 if(ids[0]!=1||ids[1]!=2)throw std::runtime_error("bridge top-k tie mismatch");close(weights[0],.5f);close(weights[1],.5f);
#endif
#if defined(STRATA_FACTORY_GENERATED_SWIGLU)
 float g[]={0,1,-1},u[]={2,3,4},y[3];strata_factory::swiglu_cuda(g,u,y,3,nullptr);
 for(int i=0;i<3;++i)close(y[i],g[i]/(1+std::exp(-g[i]))*u[i]);
#endif
#if defined(STRATA_FACTORY_GENERATED_MOE_COMBINE)
 float p[]={1,2,3,4},w[]={.25f,.75f},s[]={1,2},o[2];strata_factory::combine_cuda(p,w,s,o,2,2,nullptr);close(o[0],3.5f);close(o[1],5.5f);
#endif
 std::cout<<"{\"host_bridge_arithmetic\":true,\"cuda_transport_validated\":false,\"full_model_inference_validated\":false}\n";return 0;
}
'''


def _patch_callsites(checkout, algorithms):
    changed = {}
    router = checkout/'src/kernels/cuda/router_top10.cu'
    shared = checkout/'src/kernels/cuda/shared_expert.cu'
    if 'router' in algorithms:
        text = router.read_text()
        anchor = ('void router_top10(const float* logits, int n_tokens, int n_expert, int k, int* ids, float* weights,\n'
                  '                  void* stream) {')
        if text.count(anchor) != 1:
            raise StageFailure('upstream_callsite_changed', 'Pinned router entrypoint no longer matches the reviewed integration')
        text = '#include "generated_bridge.h"\n'+text.replace(anchor, anchor+'''
#if defined(STRATA_FACTORY_GENERATED_ROUTER)
    ::strata_factory::route_cuda(logits,n_tokens,n_expert,k,ids,weights,stream);
    return;
#endif
''', 1)
        router.write_text(text)
        changed[str(router.relative_to(checkout))] = digest(router)
    if 'swiglu' in algorithms or 'moe_combine' in algorithms:
        text = '#include "generated_bridge.h"\n'+shared.read_text()
        if 'swiglu' in algorithms:
            anchor = 'swiglu_kernel<<<g_ff, THREADS, 0, (cudaStream_t) stream>>>(gate, up, gate, (int) n_ff);'
            # Do not replace native_swiglu_kernel, whose fast-math semantics are different.
            pattern = r'(?<![A-Za-z_])'+re.escape(anchor)
            if len(re.findall(pattern,text)) != 2:
                raise StageFailure('upstream_callsite_changed', 'Expected both canonical shared-expert SwiGLU launch sites')
            text = re.sub(pattern, '''
#if defined(STRATA_FACTORY_GENERATED_SWIGLU)
            ::strata_factory::swiglu_cuda(gate,up,gate,(int)n_ff,stream);
#else
            '''+anchor+'''
#endif
''', text)
        if 'moe_combine' in algorithms:
            anchor = ('void moe_combine(const float* parts, const float* weights, const float* shared, float* y, int64_t n_embd,\n'
                      '                 int64_t k, void* stream) {')
            if text.count(anchor) != 1:
                raise StageFailure('upstream_callsite_changed', 'Pinned MoE combine entrypoint no longer matches')
            text = text.replace(anchor, anchor+'''
#if defined(STRATA_FACTORY_GENERATED_MOE_COMBINE)
    if(n_embd<=0 || k<=0) return;
    ::strata_factory::combine_cuda(parts,weights,shared,y,n_embd,k,stream);
    return;
#endif
''', 1)
        shared.write_text(text)
        changed[str(shared.relative_to(checkout))] = digest(shared)
    # The original session starts capture directly; it does not warm these host
    # buffers. Prepare process-lifetime pinned staging from real geometry before
    # either per-layer or whole-token capture begins. No math is executed here.
    session = checkout/'src/core/session.cpp'
    text = '#include "generated_bridge.h"\n'+session.read_text()
    for anchor in ('if (gr.captured) return true;', 'if (tg.captured) return true;'):
        if text.count(anchor) != 1:
            raise StageFailure('upstream_callsite_changed','Pinned session capture preparation anchor changed')
        text = text.replace(anchor,anchor+'''
#if defined(STRATA_FACTORY_GENERATED_BRIDGE)
    ::strata_factory::prepare_cuda_pool(
        (std::size_t)(g.n_expert+3*g.n_expert_used+3*g.n_ff_shexp+g.n_embd*(g.n_expert_used+2)),
        (std::size_t)(g.n_layers*20+128));
#endif
''',1)
    session.write_text(text)
    changed[str(session.relative_to(checkout))] = digest(session)
    return changed


def _integration_cmake(algorithms):
    macros = ' '.join('STRATA_FACTORY_GENERATED_'+name.upper()+'=1' for name in algorithms)
    return '''# Generated source is compiled into the actual CUDA model engine; no native Ascend claim.
if(STRATA_ENABLE_CUDA)
  if(NOT TARGET strata_kernels)
    message(FATAL_ERROR "Generated integration requires the actual STRATA CUDA kernel target")
  endif()
  find_package(CUDAToolkit REQUIRED)
  add_library(strata_factory_generated_core STATIC
    "${CMAKE_CURRENT_SOURCE_DIR}/factory_generated_core/src/strata_core.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/factory_generated_core/integration/generated_bridge.cpp"
    "${CMAKE_CURRENT_SOURCE_DIR}/factory_generated_core/integration/cuda_transport.cu")
  target_compile_features(strata_factory_generated_core PRIVATE cxx_std_20)
  set_target_properties(strata_factory_generated_core PROPERTIES CUDA_STANDARD 17 CUDA_STANDARD_REQUIRED ON)
  target_include_directories(strata_factory_generated_core PUBLIC
    "${CMAKE_CURRENT_SOURCE_DIR}/factory_generated_core/include"
    "${CMAKE_CURRENT_SOURCE_DIR}/factory_generated_core/integration")
  target_compile_definitions(strata_factory_generated_core PRIVATE '''+macros+''')
  target_compile_definitions(strata_kernels PRIVATE '''+macros+''')
  target_compile_definitions(strata_engine PRIVATE STRATA_FACTORY_GENERATED_BRIDGE=1)
  target_link_libraries(strata_factory_generated_core PUBLIC CUDA::cudart)
  target_link_libraries(strata_kernels PUBLIC strata_factory_generated_core)
endif()
'''


def integrate_generated_candidate(ctx, inputs):
    source = inputs['source'].read_json()
    generated = inputs['generated'].read_json()
    if source.get('commit_sha') != PIN or generated.get('commit_sha') != PIN:
        raise StageFailure('source_pin_mismatch', 'Candidate integration requires both pristine and generated source at the reviewed STRATA commit')
    if generated.get('schema') != 'strata.constructed.source.v1':
        raise StageFailure('generated_source_invalid', 'Full candidate requires a verified generated source project')
    from .construction_pipeline import _checked_project
    generated_dir = _checked_project(generated)
    algorithms = generated.get('algorithms')
    if not isinstance(algorithms,list) or not algorithms or len(set(algorithms)) != len(algorithms) or any(name not in ALGORITHMS for name in algorithms):
        raise StageFailure('generated_algorithm_not_integrated', 'Only source-derived router, SwiGLU and MoE combine have actual full-engine integration callsites', {'algorithms': algorithms})
    for name in ('src/strata_core.cpp','include/strata_core.h'):
        if name not in generated['files']:
            raise StageFailure('generated_source_invalid', 'Required generated computation file is not fingerprinted: '+name)
    pristine = Path(source['source_dir']).resolve(strict=True)
    status = ctx.run_command(['git','status','--porcelain','--untracked-files=no'],cwd=pristine)
    head = ctx.run_command(['git','rev-parse','HEAD'],cwd=pristine)['stdout'].strip()
    if status['stdout'].strip() or head != PIN:
        raise StageFailure('baseline_modified', 'Generated candidate must start from the pristine pinned source')
    checkout = ctx.workspace/'generated-candidate'
    ctx.run_command(['git','clone','--local','--no-hardlinks',str(pristine),str(checkout)],timeout=180)
    ctx.run_command(['git','checkout','--detach',PIN],cwd=checkout)
    copied = checkout/'factory_generated_core'
    for relative, expected in generated['files'].items():
        src = (generated_dir/relative).resolve(strict=True)
        dest = copied/relative
        if not src.is_relative_to(generated_dir) or not dest.resolve().is_relative_to(copied.resolve()) or digest(src) != expected:
            raise StageFailure('generated_source_changed', relative)
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dest)
    integration = copied/'integration'
    integration.mkdir()
    for name, content in [('generated_bridge.h',BRIDGE_HEADER),('generated_bridge.cpp',BRIDGE_SOURCE),
                          ('cuda_transport.cu',CUDA_TRANSPORT),('host_bridge_test.cpp',HOST_TRANSPORT_TEST)]:
        (integration/name).write_text(content)
    callsites = _patch_callsites(checkout, algorithms)
    (integration/'generated_core.cmake').write_text(_integration_cmake(algorithms))
    root_cmake = checkout/'CMakeLists.txt'
    root_cmake.write_text(root_cmake.read_text()+'\ninclude("${CMAKE_CURRENT_SOURCE_DIR}/factory_generated_core/integration/generated_core.cmake")\n')
    callsites['CMakeLists.txt'] = digest(root_cmake)
    # Exercise the exact bridge and copied generated computation using a host-only
    # transport. Device transfer and full model execution remain separate checks.
    compiler = shutil.which('c++') or shutil.which('g++') or 'c++'
    binary = ctx.workspace/'generated-bridge-host-test'
    macros = ['-DSTRATA_FACTORY_GENERATED_'+name.upper()+'=1' for name in algorithms]
    ctx.run_command([compiler,'-std=c++20','-O2',*macros,'-I',str(copied/'include'),'-I',str(integration),
        str(copied/'src/strata_core.cpp'),str(integration/'generated_bridge.cpp'),str(integration/'host_bridge_test.cpp'),'-o',str(binary)],cwd=checkout,timeout=180)
    receipt_path = ctx.workspace/'host-bridge-calls.json'
    result = ctx.run_command([str(binary)],cwd=checkout,env={'STRATA_FACTORY_TRACE_PATH':str(receipt_path)})
    host_receipt = inspect_generated_calls(receipt_path,algorithms)
    tracked = ctx.run_command(['git','ls-files','-z'],cwd=checkout)
    original_paths = Path(tracked['stdout_path']).read_bytes().split(b'\0')
    # Build inputs include the untouched engine as well as patched callsites.
    # Fingerprint every tracked original file so an unlisted source change cannot
    # enter the full candidate build under the same commit label.
    source_files = {name.decode():digest(checkout/name.decode()) for name in original_paths if name}
    checked_files = {str(path.relative_to(checkout)):digest(path) for path in copied.rglob('*') if path.is_file()}
    checked_files.update(source_files)
    return {'implementation':ctx.write_json('generated-candidate.json',{
        'schema':'factory.strata.generated_candidate.v1','source_dir':str(checkout),'commit_sha':PIN,
        'source_artifact_id':inputs['source'].id,'source_manifest_sha256':inputs['source'].sha256,
        'generated_artifact_id':inputs['generated'].id,'generated_manifest_sha256':inputs['generated'].sha256,
        'generated_source_dir':str(generated_dir),'generated_files':generated['files'],'files':checked_files,
        'original_tracked_files':len(source_files),
        'algorithms':algorithms,'callsites':callsites,
        'execution_strategy':'cuda+host_generated_cores',
        'cuda_build_integrated':True,'cuda_compile_validated':False,'cuda_device_validated':False,
        'cuda_graph_transport_implemented':True,'cuda_graph_capture_validated':False,
        'cuda_full_model_runtime_validated':False,
        'cuda_scheduling_contract':{
            'cuda_api':'CUDA stream capture with cudaLaunchHostFunc (CUDA 10+) and pinned async transfers',
            'buffer_preparation':'Geometry-sized pinned staging before session_capture/session_capture_token',
            'cache_identity':'stream, capture id, operation, tensor pointers and shapes',
            'lifetime':'Process lifetime; staging outlives every captured graph host node',
            'replay':'Pinned generation driver, one model process, serialized graph replay; concurrent reuse is refused',
            'callback':'Only generated CPU computation; no CUDA API calls',
            'capacity':'Unprepared shapes or exhausted pinned slots fail explicitly'},
        'native_ascend_graph_ready':False,'missing_native_operations':MISSING_NATIVE,
        'host_bridge_verification':{'result':json.loads(result['stdout']),'calls':host_receipt,
            'binary_path':str(binary),'binary_sha256':digest(binary),
            'receipt_path':str(receipt_path),'receipt_sha256':digest(receipt_path),
            'stdout_path':result['stdout_path'],'stderr_path':result['stderr_path']},
        'full_inference_validated':False})}


def validate_generated_candidate(path):
    value = json_object(Path(path),{'schema':str,'source_dir':str,'commit_sha':str,'files':dict,'algorithms':list,
        'generated_manifest_sha256':str,'execution_strategy':str,'callsites':dict})
    if value['schema'] != 'factory.strata.generated_candidate.v1' or value['commit_sha'] != PIN or value['execution_strategy'] != 'cuda+host_generated_cores':
        raise StageFailure('generated_candidate_invalid','Unknown generated candidate integration')
    directory = Path(value['source_dir']).resolve(strict=True)
    required = ['CMakeLists.txt','factory_generated_core/src/strata_core.cpp',
        'factory_generated_core/include/strata_core.h','factory_generated_core/integration/generated_bridge.cpp',
        'factory_generated_core/integration/generated_core.cmake','factory_generated_core/integration/cuda_transport.cu']
    if not value['algorithms'] or any(name not in ALGORITHMS for name in value['algorithms']) or any(name not in value['files'] for name in required) or not value['callsites']:
        raise StageFailure('generated_candidate_invalid','Generated candidate has no checked actual computation and build integration')
    for relative, expected in value['files'].items():
        file = (directory/relative).resolve(strict=True)
        if not file.is_relative_to(directory) or digest(file) != expected:
            raise StageFailure('generated_candidate_changed','Integrated source bytes changed: '+relative)
    return {'commit_sha':PIN,'generated_manifest_sha256':value['generated_manifest_sha256'],
        'algorithms':value['algorithms'],'execution_strategy':value['execution_strategy'],
        'native_ascend_graph_ready':False,'full_inference_validated':False}


def inspect_generated_calls(path, algorithms):
    path = Path(path)
    if not path.is_file():
        raise StageFailure('generated_execution_receipt_missing','The candidate process did not publish actual generated-core call counts')
    try: value = json.loads(path.read_text())
    except (ValueError,UnicodeDecodeError) as error:
        raise StageFailure('generated_execution_receipt_invalid','Invalid actual generated-core call receipt') from error
    if value.get('schema') != 'factory.generated_core.calls.v1' or value.get('execution_strategy') != 'cuda+host_generated_cores':
        raise StageFailure('generated_execution_receipt_invalid','Unknown generated-core execution strategy')
    calls = value.get('calls',{})
    missing = [name for name in algorithms if type(calls.get(name)) is not int or calls[name] <= 0]
    if missing:
        raise StageFailure('generated_algorithm_not_executed','Full model process did not consume every selected generated algorithm',{'algorithms_without_calls':missing,'actual_calls':calls})
    return value
