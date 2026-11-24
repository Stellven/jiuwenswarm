// Illustration to adapt: INFO signatures for decision and teardown, visible at -lv 4.
#include <cstdio>

// The engine defines LLAMA_LOG_INFO in llama-impl.h; this stand-in is for syntax only.
#define LLAMA_LOG_INFO(...) std::fprintf(stderr, __VA_ARGS__)

void first_decision(bool gate_set, bool admitted, unsigned cap_mib, const char * backend) {
    if (!gate_set) return;
    if (admitted) {
        LLAMA_LOG_INFO("expert_weight_cache: active cap_mib=%u backend=%s\n", cap_mib, backend);
    } else {
        LLAMA_LOG_INFO("expert_weight_cache: inactive (no capacity)\n");
    }
}

// Supply real counters only after pending readers retire.
void report_stats(bool gate_set, unsigned leases, unsigned reuses, unsigned evictions,
                  std::size_t bytes_saved, std::size_t peak_bytes) {
    if (!gate_set) return;
    LLAMA_LOG_INFO("expert_weight_cache: stats leases=%u reuses=%u evictions=%u "
                   "bytes_copied_saved=%zu peak_bytes=%zu\n",
                   leases, reuses, evictions, bytes_saved, peak_bytes);
}
