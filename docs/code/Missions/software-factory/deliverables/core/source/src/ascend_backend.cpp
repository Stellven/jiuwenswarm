#include <acl/acl.h>
#include <aclnn/acl_meta.h>
#include <aclnnop/aclnn_silu.h>
#include <aclnnop/aclnn_mul.h>
#include <mutex>
#include <stdexcept>
#include <string>
namespace strata_core {
namespace {
void check(int code,const char* op) { if(code)throw std::runtime_error(std::string(op)+" failed: "+std::to_string(code)); }
struct Storage {
 void* ptr=nullptr;size_t bytes;
 explicit Storage(size_t size):bytes(size){check(aclrtMalloc(&ptr,size,ACL_MEM_MALLOC_NORMAL_ONLY),"aclrtMalloc");}
 ~Storage(){if(ptr)aclrtFree(ptr);}
};
struct Tensor {
 aclTensor* ptr=nullptr;
 Tensor(Storage& buffer,int64_t size){int64_t shape[]={size},stride[]={1};ptr=aclCreateTensor(shape,1,ACL_FLOAT,stride,0,ACL_FORMAT_ND,shape,1,buffer.ptr);if(!ptr)throw std::runtime_error("aclCreateTensor failed");}
 ~Tensor(){if(ptr)aclDestroyTensor(ptr);}
};
struct Session {
 aclrtStream stream=nullptr;
 Session(){check(aclInit(nullptr),"aclInit");check(aclrtSetDevice(0),"aclrtSetDevice");check(aclrtCreateStream(&stream),"aclrtCreateStream");}
 ~Session(){if(stream)aclrtDestroyStream(stream);}
};
}
void ascend_swiglu(const float* gate,const float* up,float* output,int n) {
 static std::mutex mutex;const std::lock_guard<std::mutex> guard(mutex);static Session session;
 const size_t size=size_t(n)*sizeof(float);Storage g(size),u(size),s(size),y(size);Tensor gt(g,n),ut(u,n),st(s,n),yt(y,n);
 check(aclrtMemcpy(g.ptr,size,gate,size,ACL_MEMCPY_HOST_TO_DEVICE),"gate upload");
 check(aclrtMemcpy(u.ptr,size,up,size,ACL_MEMCPY_HOST_TO_DEVICE),"up upload");
 uint64_t bytes=0;aclOpExecutor* executor=nullptr;
 check(aclnnSiluGetWorkspaceSize(gt.ptr,st.ptr,&bytes,&executor),"aclnnSiluGetWorkspaceSize");
 if(bytes){Storage workspace(bytes);check(aclnnSilu(workspace.ptr,bytes,executor,session.stream),"aclnnSilu");check(aclrtSynchronizeStream(session.stream),"Silu sync");}
 else{check(aclnnSilu(nullptr,0,executor,session.stream),"aclnnSilu");check(aclrtSynchronizeStream(session.stream),"Silu sync");}
 check(aclnnMulGetWorkspaceSize(st.ptr,ut.ptr,yt.ptr,&bytes,&executor),"aclnnMulGetWorkspaceSize");
 if(bytes){Storage workspace(bytes);check(aclnnMul(workspace.ptr,bytes,executor,session.stream),"aclnnMul");check(aclrtSynchronizeStream(session.stream),"Mul sync");}
 else{check(aclnnMul(nullptr,0,executor,session.stream),"aclnnMul");check(aclrtSynchronizeStream(session.stream),"Mul sync");}
 check(aclrtMemcpy(output,size,y.ptr,size,ACL_MEMCPY_DEVICE_TO_HOST),"result download");
}
}
