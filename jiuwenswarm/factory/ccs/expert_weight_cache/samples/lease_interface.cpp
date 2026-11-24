// Illustration to adapt: express ownership at the last-reader boundary.
#include <memory>

struct StagedAllocation;
struct ExpertKey;
using ReaderLease = std::shared_ptr<const StagedAllocation>;

struct LeaseTableSketch {
    ReaderLease acquire(const ExpertKey & key);
    void release(ReaderLease & reader);
    bool evict_unleased();
};

// A graph operation shares its handle across all reads of one expert.
// Keep the handle with pending work until scheduler completion.
struct PendingReader {
    ReaderLease last_reader;

    void after_scheduler_completion(LeaseTableSketch & table) {
        table.release(last_reader);
    }
};
