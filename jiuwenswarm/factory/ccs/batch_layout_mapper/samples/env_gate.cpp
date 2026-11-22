// Illustration to adapt, not a drop-in patch.
#include <cstdio>
#include <cstdlib>
#include <cstring>

struct gate_setting {
    bool enabled;
    const char *reason;
};

// Call once at owner creation and keep the returned state.
gate_setting read_example_gate() {
    const char *value = std::getenv("EXAMPLE_GATE");
    if (value == nullptr) return {false, nullptr};
    const bool enabled = std::strcmp(value, "1") == 0;
    const char *reason = enabled ? "enabled" : "invalid value";
    std::fprintf(stderr, "example_gate: effective=%d (%s)\n", enabled, reason);
    return {enabled, reason};
}
