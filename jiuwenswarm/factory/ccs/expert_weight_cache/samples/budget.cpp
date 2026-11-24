// Illustration to adapt: guard admission arithmetic on already-aligned byte counts.
#include <algorithm>
#include <cstddef>

bool fits_admitted_pool(std::size_t requested_cap, std::size_t ledger_admission,
                        std::size_t resident_and_reserved, std::size_t aligned_cost) {
    const auto cap = std::min(requested_cap, ledger_admission);
    // The actual reservation belongs in the shared ledger's atomic admission path.
    return cap > 0 && resident_and_reserved <= cap &&
           aligned_cost <= cap - resident_and_reserved;
}
