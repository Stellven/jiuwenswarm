#pragma once
#include "ggml.h"
#include "ggml-backend.h"
#ifdef __cplusplus
extern "C" {
#endif
struct ggml_cpu_expert_context;
struct ggml_cpu_expert_view { const void * data; void * lease; uint64_t generation; };
// Admit exact ordinary CPU types, including the pinned borrowed mmap wrapper.
// Do not accept arbitrary host buffers or names (e.g. CUDA_Host / CPU_REPACK).
static inline bool ggml_cpu_expert_buffer_supported(ggml_backend_buffer_t buffer) {
    if (!buffer) { return false; }
    ggml_backend_buffer_type_t type = ggml_backend_buffer_get_type(buffer);
    if (type == ggml_backend_cpu_buffer_type()) { return true; }
    // The public factory yields the private CPU_Mapped type without owning data.
    ggml_backend_buffer_t probe = ggml_backend_cpu_buffer_from_ptr(NULL, 0);
    if (!probe) { return false; }
    bool supported = type == ggml_backend_buffer_get_type(probe);
    ggml_backend_buffer_free(probe);
    return supported;
}
// Create from checked process configuration. NULL means both switches are off.
GGML_BACKEND_API struct ggml_cpu_expert_context * ggml_cpu_expert_create(void);
GGML_BACKEND_API void ggml_cpu_expert_destroy(struct ggml_cpu_expert_context * ctx);
GGML_BACKEND_API bool ggml_cpu_expert_register(struct ggml_cpu_expert_context * ctx, const struct ggml_tensor * tensor, int fd, uint64_t offset);
GGML_BACKEND_API bool ggml_cpu_expert_validate(struct ggml_cpu_expert_context * ctx);
// 0: original complete tensor path; 1: ready compact lease; -1: failed demand.
GGML_BACKEND_API int ggml_cpu_expert_acquire(const struct ggml_tensor * tensor, int expert, struct ggml_cpu_expert_view * view);
GGML_BACKEND_API void ggml_cpu_expert_release(struct ggml_cpu_expert_view * view);
#ifdef __cplusplus
}
#endif
