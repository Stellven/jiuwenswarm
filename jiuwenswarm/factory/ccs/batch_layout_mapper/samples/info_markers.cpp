// Illustration to adapt, not a drop-in patch.
#include <cstdio>

// Standalone stand-in. In stock common/log.h, use LOG_INFV(4, ...).
#define LOG_INFV(level, ...) log_at(level, __VA_ARGS__)

template <class... Args>
void log_at(int level, const char *format, Args... args) {
    constexpr int verbosity = 4;
    if (verbosity >= level) {
        std::fprintf(stderr, format, args...);
    }
}

void example_first_use(bool gate_set, const char *bypass_reason, unsigned width) {
    if (!gate_set) return;
    if (bypass_reason) {
        LOG_INFV(4, "example: inactive (%s)\n", bypass_reason);
    } else {
        LOG_INFV(4, "example: active width=%u\n", width);
    }
}

void example_orderly_exit(bool gate_set, unsigned decisions, unsigned bypasses) {
    if (!gate_set) return;
    LOG_INFV(4, "example: stats decisions=%u bypasses=%u\n", decisions, bypasses);
}
