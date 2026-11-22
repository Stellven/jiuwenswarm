// Illustration to adapt: read the gate once during context construction.
#include <cstdio>
#include <cstdlib>
#include <cstring>

bool read_opt_in() {
    const char * gate = std::getenv("LLAMA_EXPERT_CACHE");
    const bool enabled = gate != nullptr && std::strcmp(gate, "1") == 0;
    // Use engine INFO logging and keep this opt-in diagnostic out of the hot loop.
    if (enabled) {
        std::fprintf(stderr, "LLAMA_EXPERT_CACHE effective=1\n");
    }
    return enabled;
}
