// Illustration to adapt. Charges here are normalized physical bytes for one phase.
#include <cstdint>
#include <initializer_list>

bool example_fits(std::uint64_t cap, std::initializer_list<std::uint64_t> charges) {
    auto remaining = cap;
    for (const auto bytes : charges) {
        if (bytes > remaining) {
            return false;
        }
        remaining -= bytes;
    }
    return true;
}

static_assert(sizeof(std::uint64_t) == 8);
