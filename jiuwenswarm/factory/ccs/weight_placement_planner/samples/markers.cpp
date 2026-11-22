// Illustration to adapt. Take counts from the committed load and use one owner.
#include <cstddef>
#include "log.h"
#include "llama-impl.h"

// Called once after the load decision. A null reason denotes a successful load.
void example_load_result(bool requested, const char * reason, std::size_t bytes) {
    if (!requested) {
        return;
    }
    // Capture at -lv 4. Use LOG_INF in common code, LLAMA_LOG_INFO in src.
    if (reason) {
        LLAMA_LOG_INFO("example_placement: inactive (%s)\n", reason);
    } else {
        LLAMA_LOG_INFO("example_placement: active bytes=%zu\n", bytes);
    }
}

// Called once on orderly shutdown while common logging is still alive.
void example_exit(bool requested, std::size_t count) {
    if (requested) {
        LOG_INF("example_placement: stats rows=%zu\n", count);
    }
}
