// Illustration to adapt. This is not a drop-in patch.
#include <cstddef>
#include <cstdio>

// Standalone shim. Use llama-impl.h in an authorized engine translation unit.
#define LLAMA_LOG_INFO(...) std::fprintf(stderr, __VA_ARGS__)

// Caller selects a single first-use outcome. Run the engine with -lv 4.
void example_first_use(bool gate_set, bool ready, std::size_t capacity_bytes, const char * reason) {
    if (!gate_set) return;
    if (ready) {
        LLAMA_LOG_INFO("runtime_event_recorder: active capacity_bytes=%zu\n", capacity_bytes);
    } else {
        LLAMA_LOG_INFO("runtime_event_recorder: inactive (%s)\n", reason);
    }
}

// Call once after the cold drain, with its final counters.
void example_exit(bool gate_set, std::size_t written, std::size_t lost, std::size_t bytes) {
    if (!gate_set) return;
    LLAMA_LOG_INFO("runtime_event_recorder: stats events=%zu lost=%zu bytes=%zu\n",
                   written, lost, bytes);
}
