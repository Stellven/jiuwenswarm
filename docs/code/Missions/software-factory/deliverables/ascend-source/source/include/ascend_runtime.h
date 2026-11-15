#pragma once
#include <acl/acl.h>
#include <aclnn/acl_meta.h>
#include <aclnnop/aclnn_add.h>
#include <aclnnop/aclnn_div.h>
#include <aclnnop/aclnn_maximum.h>
#include <aclnnop/aclnn_mul.h>
#include <aclnnop/aclnn_silu.h>
#include <aclnnop/aclnn_softmax.h>
#include <aclnnop/aclnn_sort.h>
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
inline void add(Session& s,const Tensor& a,const Tensor& b,Tensor& out){Scalar alpha(1.f);run(s,"aclnnAdd",aclnnAddGetWorkspaceSize,aclnnAdd,a.ptr,b.ptr,alpha.ptr,out.ptr);}
inline void divide(Session& s,const Tensor& a,const Tensor& b,Tensor& out){run(s,"aclnnDiv",aclnnDivGetWorkspaceSize,aclnnDiv,a.ptr,b.ptr,out.ptr);}
inline void maximum(Session& s,const Tensor& a,const Tensor& b,Tensor& out){run(s,"aclnnMaximum",aclnnMaximumGetWorkspaceSize,aclnnMaximum,a.ptr,b.ptr,out.ptr);}
inline void mul(Session& s,const Tensor& a,const Tensor& b,Tensor& out){run(s,"aclnnMul",aclnnMulGetWorkspaceSize,aclnnMul,a.ptr,b.ptr,out.ptr);}
}
