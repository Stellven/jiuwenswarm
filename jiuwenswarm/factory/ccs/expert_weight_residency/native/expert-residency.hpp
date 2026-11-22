#pragma once
#include <algorithm>
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace expert_weight {
struct counters {
    size_t reserved_bytes = 0, outstanding_bytes = 0, active_leases = 0;
    size_t peak_bytes = 0, peak_io_bytes = 0, fills = 0, hits = 0, joined = 0, bypass = 0, failures = 0;
};
class cache {
    struct entry {
        std::vector<uint8_t> bytes;
        uint64_t generation = 0, last = 0;
        size_t readers = 0;
        bool loading = true;
        std::exception_ptr error;
    };
    std::mutex mutex;
    std::condition_variable changed;
    std::map<std::string, std::shared_ptr<entry>> entries;
    std::set<std::string> warm;
    size_t capacity, io_limit, max_entries;
    uint64_t sequence = 0;
    bool cancelled = false;
    counters counts;
public:
    class lease {
        friend class cache;
        cache * owner = nullptr;
        std::shared_ptr<entry> value;
        lease(cache * c, std::shared_ptr<entry> e) : owner(c), value(std::move(e)) {}
    public:
        lease() = default;
        lease(const lease &) = delete;
        lease & operator=(const lease &) = delete;
        lease(lease && other) noexcept : owner(other.owner), value(std::move(other.value)) { other.owner = nullptr; }
        ~lease() { release(); }
        const void * data() const { return value ? value->bytes.data() : nullptr; }
        uint64_t generation() const { return value ? value->generation : 0; }
        void release() {
            if (!owner) { return; }
            std::lock_guard<std::mutex> lock(owner->mutex);
            --value->readers;
            --owner->counts.active_leases;
            owner->changed.notify_all();
            owner = nullptr;
            value.reset();
        }
    };
    cache(size_t bytes, size_t io_bytes, size_t slots, std::set<std::string> hot = {}) :
        warm(std::move(hot)), capacity(bytes), io_limit(io_bytes), max_entries(slots) {
        if (!capacity || !io_limit || io_limit > capacity || !max_entries) { throw std::invalid_argument("invalid expert budget"); }
    }
    ~cache() { if (counts.active_leases || counts.outstanding_bytes) { std::terminate(); } }
    void protect(const std::string & key) { std::lock_guard<std::mutex> lock(mutex); warm.insert(key); }
    counters snapshot() { std::lock_guard<std::mutex> lock(mutex); return counts; }
    void cancel() { std::lock_guard<std::mutex> lock(mutex); cancelled = true; changed.notify_all(); }
    lease acquire(const std::string & key, size_t bytes, const std::function<void(void *,size_t)> & fill) {
        std::unique_lock<std::mutex> lock(mutex);
        if (cancelled) { throw std::runtime_error("expert acquisition cancelled"); }
        auto found = entries.find(key);
        if (found != entries.end()) {
            auto e = found->second;
            if (e->loading) { ++counts.joined; }
            ++e->readers; ++counts.active_leases;
            changed.wait(lock, [&] { return !e->loading || cancelled; });
            if (cancelled || e->error || e->bytes.size() != bytes) {
                --e->readers; --counts.active_leases;
                if (e->error) { std::rethrow_exception(e->error); }
                throw std::runtime_error("expert acquisition cancelled or identity changed");
            }
            ++counts.hits; e->last = ++sequence;
            return lease(this, e);
        }
        if (!bytes || bytes > capacity || bytes > io_limit || bytes > io_limit-counts.outstanding_bytes) {
            ++counts.bypass; return {};
        }
        while (bytes > capacity-counts.reserved_bytes || entries.size() >= max_entries) {
            auto victim = entries.end();
            for (auto it = entries.begin(); it != entries.end(); ++it) {
                if (it->second->loading || it->second->readers || warm.count(it->first)) { continue; }
                if (victim == entries.end() || it->second->last < victim->second->last) { victim = it; }
            }
            if (victim == entries.end()) { ++counts.bypass; return {}; }
            counts.reserved_bytes -= victim->second->bytes.size(); entries.erase(victim);
        }
        auto e = std::make_shared<entry>();
        e->bytes.resize(bytes); e->generation = ++sequence; e->last = sequence;
        entries.emplace(key, e);
        counts.reserved_bytes += bytes; counts.outstanding_bytes += bytes;
        counts.peak_bytes = std::max(counts.peak_bytes, counts.reserved_bytes);
        counts.peak_io_bytes = std::max(counts.peak_io_bytes, counts.outstanding_bytes);
        lock.unlock();
        std::exception_ptr failure;
        try { fill(e->bytes.data(), bytes); } catch (...) { failure = std::current_exception(); }
        lock.lock();
        counts.outstanding_bytes -= bytes; e->loading = false;
        if (cancelled && !failure) { failure = std::make_exception_ptr(std::runtime_error("expert fill cancelled")); }
        if (failure) {
            e->error = failure; ++counts.failures;
            std::vector<uint8_t>().swap(e->bytes);
            counts.reserved_bytes -= bytes; entries.erase(key); changed.notify_all();
            std::rethrow_exception(failure);
        }
        ++counts.fills; ++e->readers; ++counts.active_leases; changed.notify_all();
        return lease(this, e);
    }
};
}
