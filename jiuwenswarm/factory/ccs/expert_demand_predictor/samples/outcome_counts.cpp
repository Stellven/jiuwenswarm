// Illustration to adapt, not a drop-in patch. Values describe mock consumption.
#include <cstdint>

struct ExampleCounts {
    unsigned hits = 0;
    unsigned misses = 0;
    std::uint64_t wasted_bytes = 0;
};

void observe_actual(ExampleCounts & counts, bool was_forecast) {
    if (was_forecast) {
        ++counts.hits;
    } else {
        ++counts.misses;
    }
}

// Call once per uniquely charged, admitted range at settlement.
// Learning that the router selected an ID is separate from readiness evidence.
void settle_range(ExampleCounts & counts, std::uint64_t admitted_bytes,
                  std::uint64_t proven_useful_bytes) {
    if (proven_useful_bytes <= admitted_bytes) {
        counts.wasted_bytes += admitted_bytes - proven_useful_bytes;
    }
}
