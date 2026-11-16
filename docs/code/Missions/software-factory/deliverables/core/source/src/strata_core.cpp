#include "strata_core.h"
#include "cuda_cpu_runtime.h"
#include <cmath>
#include <stdexcept>
using std::exp;using std::expf;using std::fmax;using std::fmaxf;using std::fmin;using std::fminf;
namespace kernel_49ab87035bb021f7_scope {
constexpr int RT_MAX_THREADS = 512;
static cuda_cpu::Task kernel_49ab87035bb021f7(cuda_cpu::Span<const float> logits, int n_tokens, int n_expert, int k, cuda_cpu::Span<int> ids, cuda_cpu::Span<float> weights, cuda_cpu::Block& block, cuda_cpu::Thread& thread) {
    const auto threadIdx = thread.index(); const auto blockIdx = block.index();
    const auto blockDim = block.dimensions(); const auto gridDim = block.grid(); const int warpSize = 32;

    
    
    auto* s_raw = block.dynamic_shared<unsigned char>();
    const size_t taken_bytes = ((size_t) n_expert + 15u) & ~(size_t) 15u;
    unsigned char* s_taken = s_raw;
    double* s_ex = (double*) (s_raw + taken_bytes);
    auto* s_red = block.shared<float>("s_red", RT_MAX_THREADS / 32);
    auto* s_rid = block.shared<int>("s_rid", RT_MAX_THREADS / 32);
    auto& s_sum = *block.shared<double>("s_sum", 1);

    const int t = blockIdx.x;
    if (t >= n_tokens) co_return;
    const int tid = threadIdx.x;
    const int nt = blockDim.x;
    auto l = logits + (size_t) t * n_expert;

    
    
    float mx = -INFINITY;
    for (int e = tid; e < n_expert; e += nt) mx = fmaxf(mx, l[e]);
    for (int off = 16; off > 0; off >>= 1) mx = fmaxf(mx, (co_await thread.shuffle_down(10,0xffffffffu, mx, off)));
    if ((tid & 31) == 0) s_red[tid >> 5] = mx;
    co_await thread.barrier(1);
    if (tid < 32) {
        const int nw = (nt + 31) >> 5;
        float v = (tid < nw) ? s_red[tid] : -INFINITY;
        for (int off = 16; off > 0; off >>= 1) v = fmaxf(v, (co_await thread.shuffle_down(11,0xffffffffu, v, off)));
        if (tid == 0) s_red[0] = v;
    }
    co_await thread.barrier(2);
    mx = s_red[0];

    
    
    for (int e = tid; e < n_expert; e += nt) s_ex[e] = exp((double) l[e] - (double) mx);
    co_await thread.barrier(3);

    
    if (tid == 0) {
        double sum = 0.0;
        for (int e = 0; e < n_expert; ++e) sum += s_ex[e];
        s_sum = sum;
    }
    co_await thread.barrier(4);
    const float inv = (float) (1.0 / s_sum);

    
    
    
    
    
    
    
    
    
    float* s_p = (float*) (s_ex + n_expert);
    for (int e = tid; e < n_expert; e += nt) s_p[e] = (float) (s_ex[e] * inv);
    co_await thread.barrier(5);

    
    
    
    
    
    
    
    
    
    
    
    
    for (int e = tid; e < n_expert; e += nt) s_taken[e] = 0;
    co_await thread.barrier(6);

    for (int i = 0; i < k; ++i) {
        float bv = -INFINITY;
        int bi = n_expert;               
        for (int e = tid; e < n_expert; e += nt) {
            if (s_taken[e]) continue;
            const float pe = s_p[e];
            if (pe > bv) { bv = pe; bi = e; }
        }
        for (int off = 16; off > 0; off >>= 1) {
            const float ov = (co_await thread.shuffle_down(12,0xffffffffu, bv, off));
            const int oi = (co_await thread.shuffle_down(13,0xffffffffu, bi, off));
            if (ov > bv || (ov == bv && oi < bi)) { bv = ov; bi = oi; }
        }
        if ((tid & 31) == 0) { s_red[tid >> 5] = bv; s_rid[tid >> 5] = bi; }
        co_await thread.barrier(7);
        if (tid < 32) {
            const int nw = (nt + 31) >> 5;
            float v = (tid < nw) ? s_red[tid] : -INFINITY;
            int ix = (tid < nw) ? s_rid[tid] : n_expert;
            for (int off = 16; off > 0; off >>= 1) {
                const float ov = (co_await thread.shuffle_down(14,0xffffffffu, v, off));
                const int oi = (co_await thread.shuffle_down(15,0xffffffffu, ix, off));
                if (ov > v || (ov == v && oi < ix)) { v = ov; ix = oi; }
            }
            if (tid == 0 && ix < n_expert) {
                ids[(size_t) t * k + i] = ix;
                weights[(size_t) t * k + i] = v;
                s_taken[ix] = 1;
            }
        }
        co_await thread.barrier(8);
    }
    co_await thread.barrier(9);

    
    if (tid == 0) {
        double s = 0.0;
        for (int i = 0; i < k; ++i) s += (double) weights[(size_t) t * k + i];
        const double sc = fmax(s, 6.103515625e-05);       
        for (int i = 0; i < k; ++i)
            weights[(size_t) t * k + i] = (float) ((double) weights[(size_t) t * k + i] / sc);
    }

    co_return;
}
}

namespace kernel_82afe71f227b1515_scope {

static cuda_cpu::Task kernel_82afe71f227b1515(cuda_cpu::Span<const float> gate, cuda_cpu::Span<const float> up, cuda_cpu::Span<float> out, int n, cuda_cpu::Block& block, cuda_cpu::Thread& thread) {
    const auto threadIdx = thread.index(); const auto blockIdx = block.index();
    const auto blockDim = block.dimensions(); const auto gridDim = block.grid(); const int warpSize = 32;

    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) co_return;
    const double x = (double) gate[i];
    out[i] = (float) (x / (1.0 + exp(-x))) * up[i];

    co_return;
}
}

namespace kernel_6f47e6c5df6f167e_scope {

static cuda_cpu::Task kernel_6f47e6c5df6f167e(cuda_cpu::Span<const float> parts, cuda_cpu::Span<const float> weights, cuda_cpu::Span<const float> shared, cuda_cpu::Span<float> y, int n_embd, int k, int has_shared, cuda_cpu::Block& block, cuda_cpu::Thread& thread) {
    const auto threadIdx = thread.index(); const auto blockIdx = block.index();
    const auto blockDim = block.dimensions(); const auto gridDim = block.grid(); const int warpSize = 32;

    const int j = blockIdx.x * blockDim.x + threadIdx.x;
    if (j >= n_embd) co_return;
    
    
    double acc = 0.0;
    for (int e = 0; e < k; ++e) acc += (double) weights[e] * (double) parts[(size_t) e * n_embd + j];
    
    if (has_shared) acc += (double) shared[j];
    y[j] = (float) acc;

    co_return;
}
}

namespace strata_core {
#ifdef STRATA_CORE_ASCEND
void ascend_swiglu(const float*,const float*,float*,int);
#endif
Routing invoke_49ab87035bb021f7(const std::vector<float>& logits,int k) {
 const int n=int(logits.size());if(n<1||n>512||k<1||k>n)throw std::invalid_argument("invalid routing shape");
 for(float v:logits)if(!std::isfinite(v))throw std::invalid_argument("non-finite router input");
 Routing result;result.ids.resize(k);result.weights.resize(k);
 cuda_cpu::launch(1, [&](cuda_cpu::Block& block,cuda_cpu::Thread& thread){return kernel_49ab87035bb021f7_scope::kernel_49ab87035bb021f7(cuda_cpu::view(logits.data(),size_t((1)*(n))), 1, n, k, cuda_cpu::view(result.ids.data(),size_t((1)*(k))), cuda_cpu::view(result.weights.data(),size_t((1)*(k))),block,thread);});
 for(int id:result.ids)if(id<0||id>=n)throw std::runtime_error("source kernel produced invalid expert index");
 for(float value:result.weights)if(!std::isfinite(value))throw std::runtime_error("source kernel produced non-finite weight");
 return result;
}
Routing route(const std::vector<float>& logits,int k) {
 const int n=int(logits.size());if(n<1||n>512||k<1||k>n)throw std::invalid_argument("invalid routing shape");
 for(float v:logits)if(!std::isfinite(v))throw std::invalid_argument("non-finite router input");
 Routing result;result.ids.resize(k);result.weights.resize(k);
 cuda_cpu::launch(1, [&](cuda_cpu::Block& block,cuda_cpu::Thread& thread){return kernel_49ab87035bb021f7_scope::kernel_49ab87035bb021f7(cuda_cpu::view(logits.data(),size_t((1)*(n))), 1, n, k, cuda_cpu::view(result.ids.data(),size_t((1)*(k))), cuda_cpu::view(result.weights.data(),size_t((1)*(k))),block,thread);});
 for(int id:result.ids)if(id<0||id>=n)throw std::runtime_error("source kernel produced invalid expert index");
 for(float value:result.weights)if(!std::isfinite(value))throw std::runtime_error("source kernel produced non-finite weight");
 return result;
}
void invoke_82afe71f227b1515(const float* gate,const float* up,float* output,int n) {
 if(!gate||!up||!output||n<1)throw std::invalid_argument("invalid activation shape");
 #ifdef STRATA_CORE_ASCEND
 ascend_swiglu(gate,up,output,n);
#else
 cuda_cpu::launch(unsigned((n+31)/32), [&](cuda_cpu::Block& block,cuda_cpu::Thread& thread){return kernel_82afe71f227b1515_scope::kernel_82afe71f227b1515(cuda_cpu::view(gate,size_t((n))), cuda_cpu::view(up,size_t((n))), cuda_cpu::view(output,size_t((n))), n,block,thread);});
#endif
}
void swiglu(const float* gate,const float* up,float* output,int n) {
 if(!gate||!up||!output||n<1)throw std::invalid_argument("invalid activation shape");
 #ifdef STRATA_CORE_ASCEND
 ascend_swiglu(gate,up,output,n);
#else
 cuda_cpu::launch(unsigned((n+31)/32), [&](cuda_cpu::Block& block,cuda_cpu::Thread& thread){return kernel_82afe71f227b1515_scope::kernel_82afe71f227b1515(cuda_cpu::view(gate,size_t((n))), cuda_cpu::view(up,size_t((n))), cuda_cpu::view(output,size_t((n))), n,block,thread);});
#endif
}
void invoke_6f47e6c5df6f167e(const float* parts,const float* weights,const float* shared,float* output,int d,int k,int has_shared) {
 if(!parts||!weights||!output||d<1||k<1||(has_shared&&!shared))throw std::invalid_argument("invalid aggregation shape");
 cuda_cpu::launch(unsigned((d+31)/32), [&](cuda_cpu::Block& block,cuda_cpu::Thread& thread){return kernel_6f47e6c5df6f167e_scope::kernel_6f47e6c5df6f167e(cuda_cpu::view(parts,size_t((d)*(k))), cuda_cpu::view(weights,size_t((k))), cuda_cpu::view(shared,size_t((d))), cuda_cpu::view(output,size_t((d))), d, k, has_shared,block,thread);});
}
void moe_combine(const float* parts,const float* weights,const float* shared,float* output,int d,int k,int has_shared) {
 if(!parts||!weights||!output||d<1||k<1||(has_shared&&!shared))throw std::invalid_argument("invalid aggregation shape");
 cuda_cpu::launch(unsigned((d+31)/32), [&](cuda_cpu::Block& block,cuda_cpu::Thread& thread){return kernel_6f47e6c5df6f167e_scope::kernel_6f47e6c5df6f167e(cuda_cpu::view(parts,size_t((d)*(k))), cuda_cpu::view(weights,size_t((k))), cuda_cpu::view(shared,size_t((d))), cuda_cpu::view(output,size_t((d))), d, k, has_shared,block,thread);});
}
const char* backend(){
#ifdef STRATA_CORE_ASCEND
 return "Ascend activation; CPU cooperative router/aggregation";
#else
 return "CPU";
#endif
}
}
