"""Real local source/build integration; no CUDA/Ascend device claims.

The integration check uses a pinned checkout when available and actual C++20
processes. Its only transport substitute is explicitly isolated in the host
bridge test executable; production builds compile cuda_transport.cu instead.
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from jiuwenswarm.software_factory.catalog import stage_catalog, validate_source
from jiuwenswarm.software_factory.contracts import Stage, StageFailure
from jiuwenswarm.software_factory.engine import FactoryService
from jiuwenswarm.software_factory.generated_candidate import (
    digest, inspect_generated_calls, validate_generated_candidate,
)
from jiuwenswarm.software_factory.strata_patch import PIN

CUDA_TEST_DOUBLE = r'''// Isolated test double. This is not an SDK or device result.
#pragma once
#include <cstdlib>
#include <cstring>
#include <functional>
#include <stdexcept>
#include <vector>
#define CUDART_CB
using cudaStream_t=void*;using cudaError_t=int;
constexpr int cudaSuccess=0,cudaHostAllocPortable=1;
enum cudaStreamCaptureStatus{cudaStreamCaptureStatusNone,cudaStreamCaptureStatusActive};
enum cudaMemcpyKind{cudaMemcpyDeviceToHost,cudaMemcpyHostToDevice};
namespace isolated_cuda {
 inline bool capturing=false,callback=false;
 inline int synchronizations=0,allocations=0;
 inline std::vector<std::function<void()>> nodes;
 inline void checked(){if(callback)throw std::runtime_error("CUDA API called inside host callback");}
 inline void replay(){for(auto& node:nodes)node();}
}
inline const char* cudaGetErrorString(int){return "isolated runtime double";}
inline int cudaHostAlloc(void** pointer,std::size_t bytes,unsigned){
 isolated_cuda::checked();if(isolated_cuda::capturing)throw std::runtime_error("allocation during capture");
 *pointer=std::malloc(bytes);++isolated_cuda::allocations;return *pointer?0:1;
}
inline int cudaStreamGetCaptureInfo(void*,cudaStreamCaptureStatus* status,unsigned long long* id){
 isolated_cuda::checked();*status=isolated_cuda::capturing?cudaStreamCaptureStatusActive:cudaStreamCaptureStatusNone;*id=isolated_cuda::capturing?123:0;return 0;
}
inline int cudaMemcpyAsync(void* target,const void* source,std::size_t bytes,cudaMemcpyKind,void*){
 isolated_cuda::checked();auto node=[=]{std::memcpy(target,source,bytes);};
 if(isolated_cuda::capturing)isolated_cuda::nodes.push_back(node);else node();return 0;
}
inline int cudaLaunchHostFunc(void*,void(*fn)(void*),void* data){
 isolated_cuda::checked();auto node=[=]{isolated_cuda::callback=true;fn(data);isolated_cuda::callback=false;};
 if(isolated_cuda::capturing)isolated_cuda::nodes.push_back(node);else node();return 0;
}
inline int cudaStreamSynchronize(void*){
 isolated_cuda::checked();if(isolated_cuda::capturing)throw std::runtime_error("synchronization during capture");
 ++isolated_cuda::synchronizations;return 0;
}
'''

CAPTURE_ORDER_TEST = r'''// Isolated capture scheduler test; no CUDA/Ascend evidence.
#include "generated_bridge.h"
#include "cuda_runtime.h"
#include <cmath>
#include <iostream>
#include <stdexcept>
void close(float a,float b){if(std::fabs(a-b)>1e-5f)throw std::runtime_error("capture computation mismatch");}
int main(){
 float logits[]={0,1,1,-1},weights[]={-99,-99};int ids[]={-99,-99};
 bool blocked=false;try{strata_factory::route_cuda(logits,1,4,2,ids,weights,nullptr);}catch(const std::runtime_error&){blocked=true;}
 if(!blocked)throw std::runtime_error("unprepared staging was accepted");
 strata_factory::prepare_cuda_pool(128,16);
 isolated_cuda::capturing=true;
 strata_factory::route_cuda(logits,1,4,2,ids,weights,reinterpret_cast<void*>(1));
 float gate[]={0,1,-1},up[]={2,3,4},activated[]={-99,-99,-99};
 strata_factory::swiglu_cuda(gate,up,activated,3,reinterpret_cast<void*>(1));
 float parts[]={1,2,3,4},w[]={.25f,.75f},shared[]={1,2},output[]={-99,-99};
 strata_factory::combine_cuda(parts,w,shared,output,2,2,reinterpret_cast<void*>(1));
 isolated_cuda::capturing=false;
 if(weights[0]!=-99||activated[0]!=-99||output[0]!=-99)throw std::runtime_error("computation occurred during capture");
 if(isolated_cuda::synchronizations||isolated_cuda::allocations!=1)throw std::runtime_error("captured transport performed sync/allocation");
 isolated_cuda::replay();
 if(ids[0]!=1||ids[1]!=2)throw std::runtime_error("captured router mismatch");
 close(weights[0],.5f);close(weights[1],.5f);close(activated[1],3.f/(1.f+std::exp(-1.f)));close(output[0],3.5f);close(output[1],5.5f);
 logits[0]=10;isolated_cuda::replay();if(ids[0]!=0)throw std::runtime_error("graph replay reused stale output");
 std::cout<<"isolated_capture_ordering_passed; device_validated=false\n";return 0;
}
'''


class ReceiptTests(unittest.TestCase):
    def test_absent_or_zero_runtime_calls_never_prove_generated_code_was_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'calls.json'
            with self.assertRaises(StageFailure) as missing:
                inspect_generated_calls(path,['router'])
            self.assertEqual(missing.exception.code,'generated_execution_receipt_missing')
            path.write_text(json.dumps({'schema':'factory.generated_core.calls.v1',
                'execution_strategy':'cuda+host_generated_cores','calls':{'router':1,'swiglu':0}}))
            self.assertEqual(inspect_generated_calls(path,['router'])['calls']['router'],1)
            with self.assertRaises(StageFailure) as unused:
                inspect_generated_calls(path,['router','swiglu'])
            self.assertEqual(unused.exception.code,'generated_algorithm_not_executed')


@unittest.skipUnless(Path('/workspace/strata/.git').is_dir() and shutil.which('c++'),
                     'Pinned local source and a C++20 compiler are needed for source integration')
class PinnedSourceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.temporary = tempfile.TemporaryDirectory(prefix='strata-generated-integration-')
        cls.root = Path(cls.temporary.name)

        def local_checkout(ctx, inputs):
            destination = ctx.workspace/'pristine'
            ctx.run_command(['git','clone','--local','--no-hardlinks','/workspace/strata',str(destination)])
            ctx.run_command(['git','checkout','--detach',PIN],cwd=destination)
            return {'source':ctx.write_json('source.json',{'schema':'factory.source.v1',
                'repository_url':'https://github.com/niko1221/strata','source_dir':str(destination),'commit_sha':PIN})}

        stages = [stage for stage in stage_catalog() if stage.id != 'source.fetch']
        stages.append(Stage('test.local_checkout','Local pinned checkout','test_acquisition','local_checkout',{},
            {'source':'source.checkout'},local_checkout,validators={'source':validate_source}))
        cls.service = FactoryService(cls.root/'runs',stages)
        cls.snapshot = cls.service.create({'goals':['implementation.generated','build.binary'],
            'target_backend':'ascend','owner_id':'isolated-test'},background=False)
        if cls.snapshot['goal_results'].get('implementation.generated',{}).get('status') != 'verified':
            errors = [(node['stage_id'],node.get('error'),node.get('attempts')) for node in cls.snapshot['nodes'] if node['status'] != 'verified']
            raise AssertionError('Actual source integration failed: '+repr(errors))
        cls.artifact = next(item for item in cls.snapshot['artifacts'] if item['kind']=='implementation.generated')
        cls.manifest_path = Path(cls.artifact['path'])
        cls.manifest = json.loads(cls.manifest_path.read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()
        super().tearDownClass()

    def test_full_candidate_consumes_generated_project_in_runtime_callsites_and_cmake(self):
        self.assertEqual(self.snapshot['status'],'blocked')
        candidate = next(node for node in self.snapshot['nodes'] if node['stage_id']=='candidate.integrate_generated')
        consumed = candidate['attempts'][0]['inputs']
        generated = next(item for item in consumed if item['kind']=='construction.source')
        self.assertEqual(generated['sha256'],self.manifest['generated_manifest_sha256'])
        directory = Path(self.manifest['source_dir'])
        generated_manifest = json.loads(Path(generated['path']).read_text())
        self.assertEqual(digest(directory/'factory_generated_core/src/strata_core.cpp'),generated_manifest['files']['src/strata_core.cpp'])
        self.assertIn('::strata_factory::route_cuda(', (directory/'src/kernels/cuda/router_top10.cu').read_text())
        shared = (directory/'src/kernels/cuda/shared_expert.cu').read_text()
        self.assertIn('::strata_factory::combine_cuda(',shared)
        self.assertEqual(shared.count('::strata_factory::swiglu_cuda('),2)
        cmake = (directory/'factory_generated_core/integration/generated_core.cmake').read_text()
        self.assertIn('factory_generated_core/src/strata_core.cpp',cmake)
        self.assertIn('target_link_libraries(strata_kernels PUBLIC strata_factory_generated_core)',cmake)
        self.assertIn('cuda_transport.cu',cmake)
        calls = self.manifest['host_bridge_verification']['calls']['calls']
        self.assertTrue(all(calls[name]>0 for name in self.manifest['algorithms']))
        self.assertFalse(self.manifest['host_bridge_verification']['result']['cuda_transport_validated'])
        self.assertFalse(self.manifest['native_ascend_graph_ready'])
        self.assertFalse(self.manifest['full_inference_validated'])

    def test_native_full_build_reports_missing_math_graph_and_does_not_compile_cuda_fallback(self):
        build = next(node for node in self.snapshot['nodes'] if node['stage_id']=='strata.build_full')
        self.assertEqual(build['status'],'blocked')
        error = build['attempts'][-1]['error']
        self.assertEqual(error['code'],'native_backend_incomplete')
        self.assertEqual(build['attempts'][0]['commands'],[])
        self.assertTrue(any('attention' in requirement for requirement in error['details']['required']))
        self.assertTrue(any(item['kind']=='implementation.generated' for item in build['attempts'][0]['inputs']))
        self.assertFalse(any(item['kind']=='build.binary' for item in self.snapshot['artifacts']))

    def test_changed_integrated_computation_is_rejected_before_full_build(self):
        path = Path(self.manifest['source_dir'])/'factory_generated_core/src/strata_core.cpp'
        original = path.read_bytes()
        try:
            path.write_bytes(original+b'\n// mutation must invalidate receipt\n')
            with self.assertRaises(StageFailure) as invalid:
                validate_generated_candidate(self.manifest_path)
            self.assertEqual(invalid.exception.code,'generated_candidate_changed')
        finally:
            path.write_bytes(original)
        self.assertEqual(validate_generated_candidate(self.manifest_path)['generated_manifest_sha256'],
                         self.manifest['generated_manifest_sha256'])

    def test_capture_ordering_with_isolated_runtime_double_never_counts_as_device_validation(self):
        directory = Path(self.manifest['source_dir'])/'factory_generated_core'
        isolated = self.root/'isolated-cuda-api-test'
        isolated.mkdir(exist_ok=True)
        (isolated/'cuda_runtime.h').write_text(CUDA_TEST_DOUBLE)
        (isolated/'capture_test.cpp').write_text(CAPTURE_ORDER_TEST)
        binary = isolated/'capture-test'
        macros = ['-DSTRATA_FACTORY_GENERATED_'+name.upper()+'=1' for name in self.manifest['algorithms']]
        command = [shutil.which('c++'),'-std=c++20','-O2',*macros,'-I',str(isolated),'-I',str(directory/'include'),
            '-I',str(directory/'integration'),str(directory/'src/strata_core.cpp'),
            str(directory/'integration/generated_bridge.cpp'),'-x','c++',str(directory/'integration/cuda_transport.cu'),
            str(isolated/'capture_test.cpp'),'-o',str(binary)]
        subprocess.run(command,check=True,capture_output=True,text=True)
        result = subprocess.run([str(binary)],check=True,capture_output=True,text=True)
        self.assertIn('isolated_capture_ordering_passed; device_validated=false',result.stdout)
        self.assertFalse(self.manifest['cuda_graph_capture_validated'])
        self.assertFalse(self.manifest['cuda_device_validated'])


if __name__=='__main__':unittest.main()
