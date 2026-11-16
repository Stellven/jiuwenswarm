#include "strata/kernels/ascend/expert_adapter.hpp"
#ifndef STRATA_ENABLE_ASCEND_EXPERTS
namespace strata::kernels::ascend {
bool compiled() { return false; }
void run_expert(const uint8_t*, const cpu::ActQ&, float*) {
    throw std::runtime_error("Ascend expert backend was requested but this build has no CANN support; no CPU/GPU fallback is permitted");
}
}
#else
#include <acl/acl.h>
#include <aclnn/acl_meta.h>
#include <aclnnop/aclnn_matmul.h>
#include <aclnnop/aclnn_silu.h>
#include <aclnnop/aclnn_mul.h>
#include <mutex>
#include <memory>

namespace strata::kernels::ascend {
bool compiled() { return true; }
namespace {
void require(int status, const char* operation) {
    if (status != 0) throw std::runtime_error(std::string(operation) + " failed, status=" + std::to_string(status));
}
struct Buffer {
    void* ptr = nullptr;
    size_t bytes;
    explicit Buffer(size_t count) : bytes(count) { if (count) require(aclrtMalloc(&ptr, count, ACL_MEM_MALLOC_NORMAL_ONLY), "aclrtMalloc"); }
    ~Buffer() { if (ptr) aclrtFree(ptr); }
    Buffer(const Buffer&) = delete;
    void upload(const float* source) { require(aclrtMemcpy(ptr, bytes, source, bytes, ACL_MEMCPY_HOST_TO_DEVICE), "upload tensor"); }
    void download(float* output) { require(aclrtMemcpy(output, bytes, ptr, bytes, ACL_MEMCPY_DEVICE_TO_HOST), "download tensor"); }
};
struct Tensor {
    aclTensor* ptr;
    Tensor(Buffer& storage, int64_t rows, int64_t columns) {
        const int64_t shape[] = {rows, columns}, stride[] = {columns, 1};
        ptr = aclCreateTensor(shape, 2, ACL_FLOAT, stride, 0, ACL_FORMAT_ND, shape, 2, storage.ptr);
        if (!ptr) throw std::runtime_error("aclCreateTensor returned null");
    }
    ~Tensor() { if (ptr) aclDestroyTensor(ptr); }
};
struct DeviceOps {
    aclrtStream stream = nullptr;
    DeviceOps() {
        require(aclInit(nullptr), "aclInit");
        const char* requested = std::getenv("STRATA_ASCEND_DEVICE");
        const int device = requested ? std::stoi(requested) : 0;
        if (device < 0) throw std::runtime_error("invalid STRATA_ASCEND_DEVICE");
        require(aclrtSetDevice(device), "aclrtSetDevice");
        require(aclrtCreateStream(&stream), "aclrtCreateStream");
    }
    ~DeviceOps() { if (stream) aclrtDestroyStream(stream); }
    void matvec(const float* weights, int rows, int columns, const float* input, float* output) {
        Buffer w(size_t(rows) * columns * sizeof(float)), x(size_t(columns) * sizeof(float)), y(size_t(rows) * sizeof(float));
        w.upload(weights); x.upload(input);
        Tensor wt(w, rows, columns), xt(x, columns, 1), yt(y, rows, 1);
        uint64_t bytes = 0; aclOpExecutor* executor = nullptr;
        require(aclnnMatmulGetWorkspaceSize(wt.ptr, xt.ptr, yt.ptr, 0, &bytes, &executor), "aclnnMatmulGetWorkspaceSize");
        Buffer workspace(bytes);
        require(aclnnMatmul(workspace.ptr, bytes, executor, stream), "aclnnMatmul");
        require(aclrtSynchronizeStream(stream), "matmul synchronize");
        y.download(output);
    }
    void swiglu(const float* gate, const float* up, int size, float* output) {
        Buffer g(size_t(size) * sizeof(float)), u(size_t(size) * sizeof(float)), silu(size_t(size) * sizeof(float)), y(size_t(size) * sizeof(float));
        g.upload(gate); u.upload(up);
        Tensor gt(g, size, 1), ut(u, size, 1), st(silu, size, 1), yt(y, size, 1);
        uint64_t bytes = 0; aclOpExecutor* executor = nullptr;
        require(aclnnSiluGetWorkspaceSize(gt.ptr, st.ptr, &bytes, &executor), "aclnnSiluGetWorkspaceSize");
        { Buffer workspace(bytes); require(aclnnSilu(workspace.ptr, bytes, executor, stream), "aclnnSilu"); require(aclrtSynchronizeStream(stream), "silu synchronize"); }
        require(aclnnMulGetWorkspaceSize(st.ptr, ut.ptr, yt.ptr, &bytes, &executor), "aclnnMulGetWorkspaceSize");
        { Buffer workspace(bytes); require(aclnnMul(workspace.ptr, bytes, executor, stream), "aclnnMul"); require(aclrtSynchronizeStream(stream), "mul synchronize"); }
        y.download(output);
    }
};
}
void run_expert(const uint8_t* blob, const cpu::ActQ& input, float* output) {
    // The host ExpertPool may call concurrently; one Ascend stream/context owns this opt-in path.
    static std::mutex mutex;
    const std::lock_guard<std::mutex> guard(mutex);
    static DeviceOps device;
    expert_q2(blob, input, output, device);
}
}
#endif
