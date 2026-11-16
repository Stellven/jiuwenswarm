#include "strata_core.h"
#include "cuda_cpu_runtime.h"
#include <cmath>
#include <stdexcept>
using std::exp;using std::expf;using std::fmax;using std::fmaxf;using std::fmin;using std::fminf;
namespace kernel_c9b0d6f190bcc119_scope {

static cuda_cpu::Task kernel_c9b0d6f190bcc119(cuda_cpu::Span<float> x, cuda_cpu::Span<const float> w, int64_t rows, int64_t cols, float eps, cuda_cpu::Block& block, cuda_cpu::Thread& thread) {
    const auto threadIdx = thread.index(); const auto blockIdx = block.index();
    const auto blockDim = block.dimensions(); const auto gridDim = block.grid(); const int warpSize = 32;


    const int lane = threadIdx.x & 31;
    const int64_t row = ((int64_t) blockIdx.x * (blockDim.x >> 5)) + (threadIdx.x >> 5);
    
    
    
    
    
    
    if (row >= rows) co_return;
    auto r = x + row * cols;
    float acc = 0.0f;
    for (int64_t c = lane; c < cols; c += 32) acc += r[c] * r[c];
    for (int off = 16; off > 0; off >>= 1) acc += (co_await thread.shuffle_down(1,0xFFFFFFFFu, acc, off));
    
    
    
    float inv = 0.0f;
    if (lane == 0) inv = rsqrtf(acc / (float) cols + eps);
    inv = (co_await thread.shuffle_index(2,0xFFFFFFFFu, inv, 0));
    for (int64_t c = lane; c < cols; c += 32) r[c] = (w ? r[c] * w[c] : r[c]) * inv;

    co_return;
}
}

namespace strata_core {
void invoke_c9b0d6f190bcc119(float* values,const float* weights,int64_t rows,int64_t cols,float epsilon) {
 if(!values||rows<1||cols<1||rows>1000000||cols>65536||!std::isfinite(epsilon)||epsilon<0)throw std::invalid_argument("invalid normalization contract");
 cuda_cpu::launch(unsigned(rows), [&](cuda_cpu::Block& block,cuda_cpu::Thread& thread){return kernel_c9b0d6f190bcc119_scope::kernel_c9b0d6f190bcc119(cuda_cpu::view(values,size_t((rows)*(cols))), cuda_cpu::view(weights,size_t((cols))), rows, cols, epsilon,block,thread);});
}
void rms_norm(float* values,const float* weights,int64_t rows,int64_t cols,float epsilon) {
 if(!values||rows<1||cols<1||rows>1000000||cols>65536||!std::isfinite(epsilon)||epsilon<0)throw std::invalid_argument("invalid normalization contract");
 cuda_cpu::launch(unsigned(rows), [&](cuda_cpu::Block& block,cuda_cpu::Thread& thread){return kernel_c9b0d6f190bcc119_scope::kernel_c9b0d6f190bcc119(cuda_cpu::view(values,size_t((rows)*(cols))), cuda_cpu::view(weights,size_t((cols))), rows, cols, epsilon,block,thread);});
}
const char* backend(){return "CPU";}
}
