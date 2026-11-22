// Illustration to adapt. Use the real option owner and INFO logger in the engine.
#include <cstdio>
#include <cstdlib>
#include <cstring>

enum class Gate { unset, enabled, invalid };

Gate example_gate() {
    static const Gate effective = [] {
        const char * raw = std::getenv("EXAMPLE_PLACEMENT_GATE");
        if (raw && std::strcmp(raw, "1") == 0) {
            std::fprintf(stderr, "example gate enabled (effective=1)\n");
            return Gate::enabled;
        }
        if (raw) {
            std::fprintf(stderr, "example gate disabled (invalid value)\n");
            return Gate::invalid;
        }
        return Gate::unset;
    }();
    return effective;
}
