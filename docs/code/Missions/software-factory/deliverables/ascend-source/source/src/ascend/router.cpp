#include "strata_core.h"
#include "ascend_runtime.h"
#include <cmath>
// Source: src/kernels/cuda/router_top10.cu sha256=4fa8260d101ba1d5c82e9ee1ee6260ca3f8a7d8020493254682dd0e597c5e94a function_sha256=6ad4e33231f928eedbfd8b924c520f4e3cd2796abb2f464697aa2ae1fbd80809
namespace strata_core::ascend_detail {
Routing native_route(const std::vector<float>& logits,int k){
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
}
