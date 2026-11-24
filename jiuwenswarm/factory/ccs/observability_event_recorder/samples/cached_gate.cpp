// Illustration to adapt. This is not a drop-in patch.
#include <cstdlib>

const char * example_output_path() {
    // A function-local static evaluates getenv once. Read before any hot hooks.
    static const char * const configured = []() -> const char * {
        const char * path = std::getenv("LLAMA_EVENT_REC");
        if (!path) return nullptr;
        return path;
    }();

    // The caller treats the empty string as an enabled configuration error.
    // Assume a fixed environment or own a copy of the enabled value at startup.
    return configured;
}
