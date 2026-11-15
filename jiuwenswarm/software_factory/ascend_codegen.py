"""Generate source-bound, device-only CANN operator graphs.

This backend is a bounded port of reviewed production expressions. It does not
reuse the cooperative CPU implementation. Recognizing a source contract proves
which arithmetic is being ported; it does not prove CANN numerical equivalence.
In particular FP64 production router/combination arithmetic becomes FP32 here
and requires the supplied task tolerances and exact expert-index checks on NPU.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from .cuda_lowering import sha256, strip_comments


_RESERVED = set('''alignas auto bool break case char const constexpr continue default
do double else extern false float for if int int64_t long nullptr return short signed
size_t static_cast struct true unsigned void volatile while __shared__ __syncthreads
__shfl_down_sync __shfl_sync __shfl_xor_sync threadIdx blockIdx blockDim gridDim
exp expf fmax fmaxf fmin fminf rsqrtf INFINITY'''.split())
_TOKEN = re.compile(r'0[xX][0-9a-fA-F]+[uUlL]*|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?[fFuUlL]*|[A-Za-z_]\w*|\S')


def source_fingerprint(record):
    """Hash exact tokens/constant values with parameter/local alpha-renaming.

    Paths and function names have no authority. Different arithmetic, casts,
    comparison, loop bounds, or file constants produce a different fingerprint.
    The reviewed table below is immutable code, never derived from caller IR.
    """
    names = {p['name']: 'p'+str(i) for i, p in enumerate(record['parameters'])}

    def canonical(text):
        result = []
        for token in _TOKEN.findall(strip_comments(text)):
            if re.fullmatch(r'[A-Za-z_]\w*', token) and token not in _RESERVED:
                if token not in names:
                    names[token] = 'v'+str(len(names))
                token = names[token]
            result.append(token)
        return result

    payload = {'parameters': [re.sub(r'\s+', '', p['type']) for p in record['parameters']],
               'body': canonical(record['body']),
               'constants': [canonical(c) for c in record.get('constants', [])]}
    return sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')))


# Reviewed against pinned STRATA production function bodies, not test harnesses.
# Fingerprints bind complete expressions and control flow; they are deliberately
# separate from discovery/CPU lowering, which continue to accept new arithmetic.
_CONTRACTS = {
    'router': {'fingerprint': '952d58536155b76bc5d410932128f4f6fe41f92e4d44cb368a0001626576935c', 'version': 'router-softmax-stable-gather-clamp-v1',
               'primitives': ['softmax', 'sort', 'add', 'maximum', 'div'],
               'graph': ['softmax over all experts', 'stable descending probability sort; ascending index ties',
                         'first k probabilities', 'ordered selected-probability sum',
                         'max(sum, 2**-14)', 'selected probabilities / denominator'],
               'precision': 'Production FP64 exp/sums with FP32 probability rounding; CANN FP32 softmax/sums. Near-tie expert IDs require exact device validation.'},
    'swiglu': {'fingerprint': '8019913d2dc829e336148f3dd61c7c8f6e2041253b13e0d70b0234b1cb50e618', 'version': 'silu-then-multiply-v1',
               'primitives': ['silu', 'mul'], 'graph': ['silu(gate)', 'FP32 silu result * up'],
               'precision': 'Production FP64 SiLU rounded to FP32 before multiplication; CANN FP32 SiLU. Requires task-tolerance device comparison.'},
    'moe_combine': {'fingerprint': 'd0a56dfb896d156b9478cd79558fefe60d6755ebef7b5cfdf54f9326ca86a7f3', 'version': 'ordered-weighted-experts-plus-shared-v1',
                    'primitives': ['mul', 'add'],
                    'graph': ['broadcast expert weights * expert rows', 'ordered expert-index addition', 'plain optional shared addition'],
                    'precision': 'Production ordered FP64 products/sum; candidate ordered FP32 products/sum. Requires task-tolerance device comparison, including cancellation cases.'},
    'rms_norm': {'fingerprint': 'f907d40b743d28e8c0163de87bbf0b7a8d0c935d1117893815d9880d90f5d7f8', 'version': 'warp32-rms-weight-before-scale-v1',
                 'primitives': ['mul', 'add', 'div', 'rsqrt'],
                 'graph': ['FP32 square', 'ascending stride-32 lane sums', '16/8/4/2/1 reduction',
                           'sum / cols + epsilon', 'rsqrt', '(x * optional weight) * inverse'],
                 'precision': 'FP32 source order retained, including weight-before-inverse multiplication; device rsqrt/division accuracy still requires task-tolerance validation.'},
}


_API_EVIDENCE = {'add': {'header_url': 'https://raw.githubusercontent.com/Celkryos/cann/e27cccb26ba2a8256c1e8ca910f78756bbcc2627/math/add/op_api/aclnn_add.h',
         'header_sha256': '5d30cbee550d3d2fe1ca0fc995f52dd4a0c61bd4157847db25f66f243a4384ea',
         'declarations': ['aclnnStatus aclnnAddGetWorkspaceSize( const aclTensor* self, const '
                          'aclTensor* other, const aclScalar* alpha, aclTensor* out, uint64_t* '
                          'workspaceSize, aclOpExecutor** executor)',
                          'aclnnStatus aclnnAdd(void* workspace, uint64_t workspaceSize, '
                          'aclOpExecutor* executor, aclrtStream stream)']},
 'mul': {'header_url': 'https://raw.githubusercontent.com/Celkryos/cann/e27cccb26ba2a8256c1e8ca910f78756bbcc2627/math/mul/op_api/aclnn_mul.h',
         'header_sha256': '3f89ead86531bcef1b220e47f56ca0cfdb8af6984581347242021a07a22442d3',
         'declarations': ['aclnnStatus aclnnMulGetWorkspaceSize(const aclTensor* self, const '
                          'aclTensor* other, aclTensor* out, uint64_t* workspaceSize, '
                          'aclOpExecutor** executor)',
                          'aclnnStatus aclnnMul(void* workspace, uint64_t workspaceSize, '
                          'aclOpExecutor* executor, aclrtStream stream)']},
 'div': {'header_url': 'https://raw.githubusercontent.com/Celkryos/cann/e27cccb26ba2a8256c1e8ca910f78756bbcc2627/math/div/op_api/aclnn_div.h',
         'header_sha256': 'cb3361933581784be778b3cac4d827dd4d6d23dbce82723ad28e96629dd7a340',
         'declarations': ['aclnnStatus aclnnDivGetWorkspaceSize( const aclTensor* self, const '
                          'aclTensor* other, aclTensor* out, uint64_t* workspaceSize, '
                          'aclOpExecutor** executor)',
                          'aclnnStatus aclnnDiv(void* workspace, uint64_t workspaceSize, '
                          'aclOpExecutor* executor, aclrtStream stream)']},
 'maximum': {'header_url': 'https://raw.githubusercontent.com/Celkryos/cann/e27cccb26ba2a8256c1e8ca910f78756bbcc2627/math/maximum/op_api/aclnn_maximum.h',
             'header_sha256': '7c0f416abd2dd0421a8e901fb8fd69d66e16d5c0d21f7dbdcf3db3be0e0769a2',
             'declarations': ['aclnnStatus aclnnMaximumGetWorkspaceSize( const aclTensor* self, '
                              'const aclTensor* other, aclTensor* out, uint64_t* workspaceSize, '
                              'aclOpExecutor** executor)',
                              'aclnnStatus aclnnMaximum(void* workspace, uint64_t workspaceSize, '
                              'aclOpExecutor* executor, aclrtStream stream)']},
 'rsqrt': {'header_url': 'https://raw.githubusercontent.com/Celkryos/cann/e27cccb26ba2a8256c1e8ca910f78756bbcc2627/math/rsqrt/op_api/aclnn_rsqrt.h',
           'header_sha256': '39ed5257b9e04b7829b0bfb6b66b2f5e7fa1f4eabfffa6a472dc82155f89c189',
           'declarations': ['aclnnStatus aclnnRsqrtGetWorkspaceSize(const aclTensor* self, '
                            'aclTensor* out, uint64_t* workspaceSize, aclOpExecutor** executor)',
                            'aclnnStatus aclnnRsqrt(void* workspace, uint64_t workspaceSize, '
                            'aclOpExecutor* executor, aclrtStream stream)']},
 'sort': {'header_url': 'https://raw.githubusercontent.com/Celkryos/cann/e27cccb26ba2a8256c1e8ca910f78756bbcc2627/math/sort/op_api/aclnn_sort.h',
          'header_sha256': 'ddf9a3502018208a2cc02e483bb316ccf38487d3fd3436e163ca012216cc9f13',
          'declarations': ['aclnnStatus aclnnSortGetWorkspaceSize(const aclTensor* self, bool '
                           'stable, int64_t dim, bool descending, aclTensor* valuesOut, aclTensor* '
                           'indicesOut, uint64_t* workspaceSize, aclOpExecutor** executor)',
                           'aclnnStatus aclnnSort(void* workspace, uint64_t workspaceSize, '
                           'aclOpExecutor* executor, const aclrtStream stream)']},
 'softmax': {'header_url': 'https://raw.githubusercontent.com/hicann/ops-nn/1338f06dc07d3d24ec3d461a99effee198f92cef/activation/softmax_v2/op_api/aclnn_softmax.h',
             'header_sha256': '6da12c867bd0ad74ba4652ec111f55e733f81587f16d427efdd7334ddaade866',
             'declarations': ['aclnnStatus aclnnSoftmaxGetWorkspaceSize(const aclTensor* self, '
                              'int64_t dim, aclTensor* out, uint64_t* workspaceSize, '
                              'aclOpExecutor** executor)',
                              'aclnnStatus aclnnSoftmax(void* workspace, uint64_t workspaceSize, '
                              'aclOpExecutor* executor, aclrtStream stream)']},
 'silu': {'header_url': 'https://raw.githubusercontent.com/hicann/ops-nn/1338f06dc07d3d24ec3d461a99effee198f92cef/activation/swish/op_api/aclnn_silu.h',
          'header_sha256': '4fc6dd472efc3296b1e27e47f224a5d501681c032fcc087cb35b0819507d3363',
          'declarations': ['aclnnStatus aclnnSiluGetWorkspaceSize(const aclTensor* self, '
                           'aclTensor* out, uint64_t* workspaceSize, aclOpExecutor** executor)',
                           'aclnnStatus aclnnSilu(void* workspace, uint64_t workspaceSize, '
                           'aclOpExecutor* executor, aclrtStream stream)']}}


def native_plan(inventory):
    operations = []
    for record in inventory['kernels'].values():
        expected = _CONTRACTS.get(record['operation'])
        fingerprint = source_fingerprint(record)
        recognized = expected is not None and fingerprint == expected['fingerprint']
        item = {'source_id': record['id'], 'operation': record['operation'],
                'source_sha256': record['source_sha256'], 'function_sha256': record['function_sha256'],
                'source_contract_fingerprint': fingerprint, 'generated': recognized,
                'generation_status': 'GENERATED' if recognized else 'UNSUPPORTED_SOURCE_CONTRACT',
                'native_compilation': 'NOT_RUN', 'device_execution': 'NOT_RUN',
                'numerical_equivalence': 'NOT_RUN'}
        if recognized:
            contract = {k: v for k, v in expected.items() if k != 'fingerprint'}
            item.update(contract=contract, contract_sha256=sha256(json.dumps(contract, sort_keys=True)),
                        implementation='src/ascend/'+record['operation']+'.cpp')
        else:
            item['reason'] = 'Complete source tokens/signature/constants do not match an implemented immutable native contract; no CPU fallback'
        operations.append(item)
    primitives = sorted({p for item in operations if item['generated'] for p in item['contract']['primitives']})
    return {'schema': 'strata.ascend.generation.v1', 'complete': all(item['generated'] for item in operations),
            'operations': operations, 'primitives': primitives,
            'required_headers': ['acl/acl.h', 'aclnn/acl_meta.h']+['aclnnop/aclnn_'+p+'.h' for p in primitives],
            'source_generation': 'GENERATED' if all(item['generated'] for item in operations) else 'PARTIAL',
            'native_compilation': 'NOT_RUN', 'device_execution': 'NOT_RUN', 'numerical_equivalence': 'NOT_RUN',
            'full_model': 'NOT_RUN', 'cpu_fallback_permitted': False,
            'precision_policy': 'Candidate CANN FP32 graphs require real-device acceptance at task tolerances; expert IDs and stable ties require exact agreement',
            'runtime_api_evidence': [
                {'url': 'https://github.com/Ascend/msprof/blob/fd5a9872692ec9a9ab7d7ecd887b8e7ea0755db8/samples/common/util_acl.h',
                 'establishes': ['aclInit', 'aclrtSetDevice', 'aclrtCreateContext', 'aclrtSetCurrentContext', 'aclrtCreateStream', 'aclrtDestroyStream', 'aclrtDestroyContext']},
                {'url': 'https://github.com/Ascend/msprof/blob/fd5a9872692ec9a9ab7d7ecd887b8e7ea0755db8/samples/mstx_with_domain/mstx_with_domain.cpp',
                 'establishes': ['aclCreateTensor dimensions/strides/storage', 'aclCreateScalar', 'aclnnAdd two-stage dispatch', 'workspace lifetime', 'aclrtMemcpy', 'aclrtMalloc']}],
            'api_evidence': {p: _API_EVIDENCE[p] for p in primitives}}


RUNTIME = r'''#pragma once
#include <acl/acl.h>
#include <aclnn/acl_meta.h>
@OP_HEADERS@
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <limits>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>
namespace strata_core::ascend_detail {
inline void check(int status,const char* op){if(status)throw std::runtime_error(std::string(op)+" failed: "+std::to_string(status));}
struct Storage {
 void* ptr=nullptr;size_t bytes;
 explicit Storage(size_t count):bytes(count){if(count)check(aclrtMalloc(&ptr,count,ACL_MEM_MALLOC_NORMAL_ONLY),"aclrtMalloc");}
 ~Storage(){if(ptr)aclrtFree(ptr);}
 Storage(const Storage&)=delete;Storage& operator=(const Storage&)=delete;
 void upload(const void* host,size_t count){if(count>bytes)throw std::runtime_error("upload overflow");check(aclrtMemcpy(ptr,bytes,host,count,ACL_MEMCPY_HOST_TO_DEVICE),"tensor upload");}
 void download(void* host,size_t count)const{if(count>bytes)throw std::runtime_error("download overflow");check(aclrtMemcpy(host,count,ptr,count,ACL_MEMCPY_DEVICE_TO_HOST),"tensor download");}
 void zero(){check(aclrtMemset(ptr,bytes,0,bytes),"device zero initialization");}
};
struct Tensor {
 aclTensor* ptr=nullptr;
 Tensor(Storage& storage,std::vector<int64_t> shape,aclDataType dtype=ACL_FLOAT,std::vector<int64_t> strides={},int64_t offset=0){
  const int64_t item=dtype==ACL_INT64?int64_t(sizeof(int64_t)):int64_t(sizeof(float));
  if(shape.empty()||offset<0||storage.bytes%size_t(item))throw std::invalid_argument("invalid tensor storage");
  if(strides.empty()){strides.resize(shape.size(),1);for(int64_t i=int64_t(shape.size())-2;i>=0;--i)strides[size_t(i)]=strides[size_t(i+1)]*shape[size_t(i+1)];}
  if(strides.size()!=shape.size())throw std::invalid_argument("invalid tensor strides");
  int64_t last=offset;for(size_t i=0;i<shape.size();++i){if(shape[i]<1||strides[i]<1||shape[i]>16777216)throw std::invalid_argument("invalid tensor dimension");last+=(shape[i]-1)*strides[i];}
  const int64_t capacity=int64_t(storage.bytes/size_t(item));if(last>=capacity)throw std::invalid_argument("tensor view exceeds storage");
  ptr=aclCreateTensor(shape.data(),shape.size(),dtype,strides.data(),offset,ACL_FORMAT_ND,&capacity,1,storage.ptr);
  if(!ptr)throw std::runtime_error("aclCreateTensor returned null");
 }
 ~Tensor(){if(ptr)aclDestroyTensor(ptr);}
 Tensor(const Tensor&)=delete;Tensor& operator=(const Tensor&)=delete;
};
struct Scalar {
 aclScalar* ptr=nullptr;
 explicit Scalar(float value){ptr=aclCreateScalar(&value,ACL_FLOAT);if(!ptr)throw std::runtime_error("aclCreateScalar returned null");}
 ~Scalar(){if(ptr)aclDestroyScalar(ptr);}
};
struct Session {
 aclrtStream stream=nullptr;aclrtContext context=nullptr;
 Session(){
  check(aclInit(nullptr),"aclInit");
  const char* requested=std::getenv("STRATA_ASCEND_DEVICE");int device=0;
  if(requested){size_t consumed=0;device=std::stoi(requested,&consumed);if(consumed!=std::string(requested).size()||device<0)throw std::invalid_argument("invalid STRATA_ASCEND_DEVICE");}
  check(aclrtSetDevice(device),"aclrtSetDevice");
  check(aclrtCreateContext(&context,device),"aclrtCreateContext");
  try{check(aclrtCreateStream(&stream),"aclrtCreateStream");}catch(...){aclrtDestroyContext(context);throw;}
 }
 ~Session(){if(stream)aclrtDestroyStream(stream);if(context)aclrtDestroyContext(context);}
 void bind(){check(aclrtSetCurrentContext(context),"aclrtSetCurrentContext");}
};
inline std::mutex& mutex(){static std::mutex value;return value;}
inline Session& session(){static Session value;return value;}
struct SessionLock{std::lock_guard<std::mutex> guard;Session& device;SessionLock():guard(mutex()),device(session()){device.bind();}};
template<class Query,class Launch,class... Args>
void run(Session& device,const char* name,Query query,Launch launch,Args... args){
 uint64_t bytes=0;aclOpExecutor* executor=nullptr;check(query(args...,&bytes,&executor),name);
 Storage workspace(bytes);check(launch(workspace.ptr,bytes,executor,device.stream),name);
 // Workspace, tensor descriptors and device buffers outlive every queued use.
 check(aclrtSynchronizeStream(device.stream),"operator stream synchronization");
}
@PRIMITIVE_WRAPPERS@
}
'''


_PRIMITIVES = {
    'add': r'''inline void add(Session& s,const Tensor& a,const Tensor& b,Tensor& out){Scalar alpha(1.f);run(s,"aclnnAdd",aclnnAddGetWorkspaceSize,aclnnAdd,a.ptr,b.ptr,alpha.ptr,out.ptr);}''',
    'mul': r'''inline void mul(Session& s,const Tensor& a,const Tensor& b,Tensor& out){run(s,"aclnnMul",aclnnMulGetWorkspaceSize,aclnnMul,a.ptr,b.ptr,out.ptr);}''',
    'div': r'''inline void divide(Session& s,const Tensor& a,const Tensor& b,Tensor& out){run(s,"aclnnDiv",aclnnDivGetWorkspaceSize,aclnnDiv,a.ptr,b.ptr,out.ptr);}''',
    'maximum': r'''inline void maximum(Session& s,const Tensor& a,const Tensor& b,Tensor& out){run(s,"aclnnMaximum",aclnnMaximumGetWorkspaceSize,aclnnMaximum,a.ptr,b.ptr,out.ptr);}''',
    'rsqrt': r'''inline void rsqrt(Session& s,const Tensor& a,Tensor& out){run(s,"aclnnRsqrt",aclnnRsqrtGetWorkspaceSize,aclnnRsqrt,a.ptr,out.ptr);}''',
}


OPERATIONS = {
'router': r'''Routing native_route(const std::vector<float>& logits,int k){
 const int n=int(logits.size());if(n<1||n>512||k<1||k>n)throw std::invalid_argument("invalid routing shape");
 for(float v:logits)if(!std::isfinite(v))throw std::invalid_argument("non-finite router input");
 SessionLock lock;auto& s=lock.device;
 Storage input(size_t(n)*sizeof(float)),probabilities(input.bytes),sorted(input.bytes),indices(size_t(n)*sizeof(int64_t));
 input.upload(logits.data(),input.bytes);Tensor x(input,{n}),p(probabilities,{n}),values(sorted,{n}),ids(indices,{n},ACL_INT64);
 // Softmax must cover ALL experts before selection and renormalization.
 run(s,"aclnnSoftmax",aclnnSoftmaxGetWorkspaceSize,aclnnSoftmax,x.ptr,int64_t(-1),p.ptr);
 // Stable descending sort preserves ascending source index for equal probabilities.
 run(s,"aclnnSort(stable)",aclnnSortGetWorkspaceSize,aclnnSort,p.ptr,true,int64_t(-1),true,values.ptr,ids.ptr);
 Tensor top(sorted,{k});Storage accum(sizeof(float)),next(sizeof(float)),clamp(sizeof(float)),denominator(sizeof(float)),weights(size_t(k)*sizeof(float));
 accum.zero();const float lower=6.103515625e-05f;clamp.upload(&lower,sizeof(lower));
 Storage* current=&accum;Storage* pending=&next;
 for(int i=0;i<k;++i){Tensor a(*current,{1}),v(sorted,{1},ACL_FLOAT,{1},i),out(*pending,{1});add(s,a,v,out);std::swap(current,pending);}
 Tensor sum(*current,{1}),limit(clamp,{1}),denom(denominator,{1}),output(weights,{k});
 maximum(s,sum,limit,denom);divide(s,top,denom,output);
 Routing result;result.ids.resize(k);result.weights.resize(k);std::vector<int64_t> wide_ids(k);
 indices.download(wide_ids.data(),size_t(k)*sizeof(int64_t));weights.download(result.weights.data(),weights.bytes);
 for(int i=0;i<k;++i){if(wide_ids[i]<0||wide_ids[i]>=n||!std::isfinite(result.weights[i]))throw std::runtime_error("invalid native routing result");result.ids[i]=int(wide_ids[i]);}
 return result;
}
''',
'swiglu': r'''void native_swiglu(const float* gate,const float* up,float* output,int n){
 if(!gate||!up||!output||n<1||n>16777216)throw std::invalid_argument("invalid activation shape");
 SessionLock lock;auto& s=lock.device;const size_t bytes=size_t(n)*sizeof(float);
 Storage g(bytes),u(bytes),activated(bytes),result(bytes);g.upload(gate,bytes);u.upload(up,bytes);
 Tensor gt(g,{n}),ut(u,{n}),st(activated,{n}),yt(result,{n});
 run(s,"aclnnSilu",aclnnSiluGetWorkspaceSize,aclnnSilu,gt.ptr,st.ptr);
 mul(s,st,ut,yt);result.download(output,bytes);
}
''',
'moe_combine': r'''void native_combine(const float* parts,const float* weights,const float* shared,float* output,int d,int k,int has_shared){
 if(!parts||!weights||!output||d<1||d>65536||k<1||k>512||(has_shared&&!shared))throw std::invalid_argument("invalid aggregation shape");
 SessionLock lock;auto& s=lock.device;const size_t bytes=size_t(d)*sizeof(float);
 Storage p(size_t(k)*bytes),w(size_t(k)*sizeof(float)),products(p.bytes),accum(bytes),next(bytes);
 p.upload(parts,p.bytes);w.upload(weights,w.bytes);accum.zero();Tensor pt(p,{k,d}),wt(w,{k,1}),terms(products,{k,d});
 // Explicit products and ordered additions retain expert order; no matmul reassociation.
 mul(s,pt,wt,terms);Storage* current=&accum;Storage* pending=&next;
 for(int e=0;e<k;++e){Tensor a(*current,{d}),term(products,{d},ACL_FLOAT,{1},int64_t(e)*d),out(*pending,{d});add(s,a,term,out);std::swap(current,pending);}
 if(has_shared){Storage shared_values(bytes);shared_values.upload(shared,bytes);Tensor a(*current,{d}),b(shared_values,{d}),out(*pending,{d});add(s,a,b,out);std::swap(current,pending);}
 current->download(output,bytes);
}
''',
'rms_norm': r'''void native_rms(float* values,const float* weights,int64_t rows,int64_t cols,float epsilon){
 if(!values||rows<1||rows>1000000||cols<1||cols>65536||rows*cols>16777216||!std::isfinite(epsilon)||epsilon<0)throw std::invalid_argument("invalid normalization contract");
 SessionLock lock;auto& s=lock.device;const int64_t padded_cols=((cols+31)/32)*32;
 const size_t bytes=size_t(rows*cols)*sizeof(float),padded_bytes=size_t(rows*padded_cols)*sizeof(float);
 Storage input(bytes),padded(padded_bytes),squares(padded_bytes),accum(size_t(rows)*32*sizeof(float)),next(accum.bytes);
 input.upload(values,bytes);padded.zero();accum.zero();
 // Padding is device-to-device copying, never host tensor arithmetic.
 for(int64_t row=0;row<rows;++row)check(aclrtMemcpy(static_cast<char*>(padded.ptr)+size_t(row*padded_cols)*sizeof(float),size_t(cols)*sizeof(float),static_cast<char*>(input.ptr)+size_t(row*cols)*sizeof(float),size_t(cols)*sizeof(float),ACL_MEMCPY_DEVICE_TO_DEVICE),"pad RMS input row");
 Tensor xpad(padded,{rows,padded_cols}),sq(squares,{rows,padded_cols});mul(s,xpad,xpad,sq);
 Storage* current=&accum;Storage* pending=&next;
 // Source lane c accumulates c,c+32,... in ascending order.
 for(int64_t base=0;base<padded_cols;base+=32){Tensor a(*current,{rows,32}),chunk(squares,{rows,32},ACL_FLOAT,{padded_cols,1},base),out(*pending,{rows,32});add(s,a,chunk,out);std::swap(current,pending);}
 // The lane-zero dependency tree is the source's shuffle-down 16/8/4/2/1 order.
 for(int64_t offset=16;offset>0;offset>>=1){Tensor left(*current,{rows,offset},ACL_FLOAT,{32,1}),right(*current,{rows,offset},ACL_FLOAT,{32,1},offset),out(*pending,{rows,offset},ACL_FLOAT,{32,1});add(s,left,right,out);std::swap(current,pending);}
 Storage divisor(sizeof(float)),eps(sizeof(float)),mean(size_t(rows)*sizeof(float)),stabilized(mean.bytes),inverse(mean.bytes),weighted(bytes),result(bytes);
 const float columns=float(cols);divisor.upload(&columns,sizeof(columns));eps.upload(&epsilon,sizeof(epsilon));
 Tensor total(*current,{rows,1},ACL_FLOAT,{32,1}),count(divisor,{1}),epsilon_tensor(eps,{1}),means(mean,{rows,1}),stable(stabilized,{rows,1}),inv(inverse,{rows,1});
 divide(s,total,count,means);add(s,means,epsilon_tensor,stable);rsqrt(s,stable,inv);
 Tensor x(input,{rows,cols}),out(result,{rows,cols});
 if(weights){Storage w(size_t(cols)*sizeof(float));w.upload(weights,w.bytes);Tensor wt(w,{cols}),wx(weighted,{rows,cols});mul(s,x,wt,wx);mul(s,wx,inv,out);}
 else mul(s,x,inv,out);
 result.download(values,bytes);
}
''',
}


_DECLARATIONS = {
    'router': 'Routing native_route(const std::vector<float>&,int);',
    'swiglu': 'void native_swiglu(const float*,const float*,float*,int);',
    'moe_combine': 'void native_combine(const float*,const float*,const float*,float*,int,int,int);',
    'rms_norm': 'void native_rms(float*,const float*,int64_t,int64_t,float);',
}

_BINDINGS = {
    'router': ('Routing', 'const std::vector<float>& logits,int k', 'return ascend_detail::native_route(logits,k);', 'route'),
    'swiglu': ('void', 'const float* gate,const float* up,float* output,int n', 'ascend_detail::native_swiglu(gate,up,output,n);', 'swiglu'),
    'moe_combine': ('void', 'const float* parts,const float* weights,const float* shared,float* output,int d,int k,int has_shared', 'ascend_detail::native_combine(parts,weights,shared,output,d,k,has_shared);', 'moe_combine'),
    'rms_norm': ('void', 'float* values,const float* weights,int64_t rows,int64_t cols,float epsilon', 'ascend_detail::native_rms(values,weights,rows,cols,epsilon);', 'rms_norm'),
}


def generate_native_files(inventory, binding_name):
    plan = native_plan(inventory)
    primitives = plan['primitives']
    headers = '\n'.join('#include <aclnnop/aclnn_'+p+'.h>' for p in primitives)
    runtime = RUNTIME.replace('@OP_HEADERS@', headers).replace('@PRIMITIVE_WRAPPERS@', '\n'.join(_PRIMITIVES[p] for p in primitives if p in _PRIMITIVES))
    files = {'include/ascend_runtime.h': runtime}
    source = '#include "strata_core.h"\n#include <stdexcept>\nnamespace strata_core {\n'
    present = sorted({item['operation'] for item in plan['operations'] if item['generated']})
    source += 'namespace ascend_detail {\n'+'\n'.join(_DECLARATIONS[op] for op in present)+'\n}\n'
    emitted = set()
    for record, native in zip(inventory['kernels'].values(), plan['operations']):
        if not native['generated']:
            continue  # Entire ASCEND CMake target fails before compilation below.
        result, parameters, body, alias = _BINDINGS[record['operation']]
        source += result+' '+binding_name(record)+'('+parameters+'){'+body+'}\n'
        if alias not in emitted:
            source += result+' '+alias+'('+parameters+'){'+body+'}\n'
            emitted.add(alias)
    source += 'const char* backend(){return "ASCEND";}\n}\n'
    files['src/strata_native.cpp'] = source
    for op in present:
        records = [r for r in inventory['kernels'].values() if r['operation'] == op]
        provenance = '\n'.join('// Source: '+r['path']+' sha256='+r['source_sha256']+' function_sha256='+r['function_sha256'] for r in records)
        files['src/ascend/'+op+'.cpp'] = '#include "strata_core.h"\n#include "ascend_runtime.h"\n#include <cmath>\n'+provenance+'\nnamespace strata_core::ascend_detail {\n'+OPERATIONS[op]+'}\n'
    files['native/manifest.json'] = json.dumps(plan, indent=2)+'\n'
    return files, plan


def find_ascend_cmake(plan):
    required = ';'.join(plan['required_headers'])
    return r'''set(AscendCL_ROOT "$ENV{ASCEND_HOME_PATH}" CACHE PATH "Real CANN toolkit root")
find_path(AscendCL_INCLUDE_DIR acl/acl.h HINTS "${AscendCL_ROOT}" PATH_SUFFIXES include)
find_path(AscendCL_OP_INCLUDE_DIR aclnn/acl_meta.h HINTS "${AscendCL_ROOT}" PATH_SUFFIXES include opp/built-in/op_impl/ai_core/tbe/op_api/include)
find_library(AscendCL_LIBRARY ascendcl HINTS "${AscendCL_ROOT}" PATH_SUFFIXES lib64 lib)
find_library(AscendCL_OPAPI_LIBRARY opapi HINTS "${AscendCL_ROOT}" PATH_SUFFIXES lib64 lib opp/built-in/op_impl/ai_core/tbe/op_api/lib)
include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(AscendCL REQUIRED_VARS AscendCL_INCLUDE_DIR AscendCL_OP_INCLUDE_DIR AscendCL_LIBRARY AscendCL_OPAPI_LIBRARY)
foreach(header @HEADERS@)
 if(NOT EXISTS "${AscendCL_INCLUDE_DIR}/${header}" AND NOT EXISTS "${AscendCL_OP_INCLUDE_DIR}/${header}")
  message(FATAL_ERROR "Missing required CANN header: ${header}; CPU fallback is prohibited")
 endif()
endforeach()
if(AscendCL_FOUND)
 add_library(AscendCL::ascendcl UNKNOWN IMPORTED)
 set_target_properties(AscendCL::ascendcl PROPERTIES IMPORTED_LOCATION "${AscendCL_LIBRARY}" INTERFACE_INCLUDE_DIRECTORIES "${AscendCL_INCLUDE_DIR};${AscendCL_OP_INCLUDE_DIR}")
 add_library(AscendCL::opapi UNKNOWN IMPORTED)
 set_target_properties(AscendCL::opapi PROPERTIES IMPORTED_LOCATION "${AscendCL_OPAPI_LIBRARY}")
endif()
'''.replace('@HEADERS@', required)
