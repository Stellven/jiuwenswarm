// Illustration to adapt, not a drop-in patch.
#include <cstdint>

// Pure arithmetic: zero means no valid aligned cut for these inputs.
// The caller owns eligibility, remaining-row accounting and fallback.
constexpr std::uint32_t aligned_capacity(std::uint32_t logical,
                                         std::uint32_t physical) {
    return physical == 0 ? 0 : logical - logical % physical;
}

static_assert(aligned_capacity(13, 8) == 8);
static_assert(aligned_capacity(24, 8) == 24);
static_assert(aligned_capacity(3, 8) == 0);
static_assert(aligned_capacity(13, 0) == 0);
