// Illustration to adapt, not a drop-in patch. Inspect INFO output with -lv 4.
#include <cstdio>

// Standalone stand-in. In a llama.cpp unit include the real LLAMA_LOG_INFO.
#define LLAMA_LOG_INFO(...) std::fprintf(stderr, __VA_ARGS__)

void first_use(bool gate_set, bool eligible, const char * settings, const char * reason) {
    if (!gate_set) return;
    if (eligible) {
        LLAMA_LOG_INFO("example_hint: active %s\n", settings);
    } else {
        LLAMA_LOG_INFO("example_hint: inactive (%s)\n", reason);
    }
}

void at_exit(bool gate_set, unsigned observations) {
    if (!gate_set) return;
    LLAMA_LOG_INFO("example_hint: stats observations=%u\n", observations);
}
