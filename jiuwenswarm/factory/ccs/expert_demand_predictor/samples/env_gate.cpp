// Illustration to adapt, not a drop-in patch. Use the target's logging facility.
#include <cstdio>
#include <cstdlib>
#include <cstring>

bool example_gate() {
    static const bool enabled = [] {
        const char * value = std::getenv("EXAMPLE_HINT");
        return value != nullptr && std::strcmp(value, "1") == 0;
    }();
    return enabled;
}

void log_example_settings(bool mapped) {
    if (example_gate()) {
        std::fprintf(stderr, "example settings: requested=1 mapped=%d\n", mapped);
    }
}
