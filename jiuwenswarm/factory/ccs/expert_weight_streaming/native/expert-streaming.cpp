#include "ggml-cpu-expert.h"
#include "ggml-backend.h"
#include "expert-residency.hpp"
#include <atomic>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <sstream>
#ifndef _WIN32
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace {
uint64_t env_bytes(const char * name) {
    const char * text = getenv(name);
    if (!text || !*text || strlen(text) > 20) { throw std::runtime_error("missing bounded expert configuration"); }
    uint64_t value = 0;
    for (const char * p = text; *p; ++p) {
        if (*p < '0' || *p > '9' || value > (UINT64_MAX-(*p-'0'))/10) { throw std::runtime_error("invalid expert budget"); }
        value = value*10 + (*p-'0');
    }
    return value;
}
bool enabled(const char * name) {
    const char * s = getenv(name);
    if (!s || strcmp(s,"0") == 0) { return false; }
    if (strcmp(s,"1") != 0) { throw std::runtime_error("expert switch must be 0 or 1"); }
    return true;
}
struct binding {
    std::shared_ptr<expert_weight::cache> slots;
    std::string identity, hot_key;
    int fd = -1;
    uint64_t offset;
    size_t stride;
    ~binding() {
#ifndef _WIN32
        if (fd >= 0) { close(fd); }
#endif
    }
};
struct token {
    std::shared_ptr<binding> source;
    expert_weight::cache::lease lease;
    token(std::shared_ptr<binding> b, expert_weight::cache::lease l) : source(std::move(b)), lease(std::move(l)) {}
};
std::atomic<size_t> registered_bindings{0};
std::mutex registry_mutex;
std::map<const ggml_tensor *, std::shared_ptr<binding>> registry;
}
struct ggml_cpu_expert_context {
    std::shared_ptr<expert_weight::cache> slots;
    std::string checkpoint;
    std::set<std::string> hot;
    std::vector<const ggml_tensor *> tensors;
    size_t warm_bytes = 0, capacity = 0, fallback = 0;
    std::set<std::string> identities, matched_hot;
};

struct ggml_cpu_expert_context * ggml_cpu_expert_create(void) {
    const bool residency = enabled("LLAMA_EXPERT_RESIDENCY");
    const bool streaming = enabled("LLAMA_EXPERT_STREAMING");
    if (!residency && !streaming) { return nullptr; }
    if (!residency || !streaming) { throw std::runtime_error("expert v1 requires both switches"); }
#ifdef _WIN32
    throw std::runtime_error("expert streaming v1 requires POSIX pread");
#else
    uint64_t available = env_bytes("LLAMA_EXPERT_PHYSICAL_BYTES");
    for (auto name : {"LLAMA_EXPERT_FIXED_BYTES", "LLAMA_EXPERT_SEQUENCE_BYTES", "LLAMA_EXPERT_WORKSPACE_BYTES", "LLAMA_EXPERT_HEADROOM_BYTES"}) {
        const auto bytes = env_bytes(name);
        if (bytes > available) { throw std::runtime_error("infeasible expert reservation"); }
        available -= bytes;
    }
    const auto cap = env_bytes("LLAMA_EXPERT_SLOT_BYTES"), io = env_bytes("LLAMA_EXPERT_IO_BYTES");
    const auto fallback = env_bytes("LLAMA_EXPERT_FALLBACK_BYTES");
    if (!cap || cap > available || cap > SIZE_MAX || !fallback || fallback > cap) { throw std::runtime_error("infeasible expert slot capacity"); }
    const char * checkpoint = getenv("LLAMA_EXPERT_CHECKPOINT");
    if (!checkpoint || strlen(checkpoint) != 64 || strspn(checkpoint,"0123456789abcdef") != 64) { throw std::runtime_error("checkpoint SHA256 required"); }
    auto ctx = std::unique_ptr<ggml_cpu_expert_context>(new ggml_cpu_expert_context);
    ctx->checkpoint = checkpoint; ctx->capacity = cap; ctx->fallback = fallback;
    const char * hot = getenv("LLAMA_EXPERT_WARM_SET");
    if (hot) {
        if (strlen(hot) > 32768) { throw std::runtime_error("warm set exceeds bound"); }
        std::stringstream in(hot); std::string key;
        while (std::getline(in,key,',')) {
            if (key.empty() || key.size() > 128 || !ctx->hot.insert(key).second) { throw std::runtime_error("invalid warm set"); }
        }
    }
    ctx->slots = std::make_shared<expert_weight::cache>(cap,io,4096);
    fprintf(stderr,"expert_weights effective slots=%llu io=%llu fallback=%llu checkpoint=%s demand_only=1\n",
        (unsigned long long)cap,(unsigned long long)io,(unsigned long long)fallback,checkpoint);
    return ctx.release();
#endif
}

bool ggml_cpu_expert_register(struct ggml_cpu_expert_context * ctx, const struct ggml_tensor * t, int fd, uint64_t offset) {
#ifndef _WIN32
    if (!ctx || !t || !t->data || !ggml_is_contiguous(t) || t->ne[2] < 1 || t->ne[3] != 1 ||
        (t->type != GGML_TYPE_F32 && t->type != GGML_TYPE_IQ2_XXS && t->type != GGML_TYPE_IQ2_XS && t->type != GGML_TYPE_IQ1_M)) { return false; }
    const size_t stride = t->nb[2], total = ggml_nbytes(t);
    struct stat st;
    if (!stride || stride > SIZE_MAX/(size_t)t->ne[2] || stride*(size_t)t->ne[2] != total ||
        fstat(fd,&st) || st.st_size < 0 || offset > (uint64_t)st.st_size || total > (uint64_t)st.st_size-offset) { return false; }
    auto b = std::make_shared<binding>(); b->slots = ctx->slots; b->offset = offset; b->stride = stride;
    b->hot_key = t->name;
    // Tensor name includes layer and role; type and row geometry fix packed layout.
    b->identity = ctx->checkpoint+":"+t->name+":"+std::to_string(t->type)+":"+std::to_string(t->ne[0])+":"+std::to_string(t->ne[1]);
    if (!ctx->identities.insert(b->identity).second) { return false; }
    b->fd = dup(fd); if (b->fd < 0) { return false; }
    size_t added = 0;
    for (int64_t e = 0; e < t->ne[2]; ++e) {
        if (ctx->hot.count(b->hot_key+":"+std::to_string(e))) {
            if (stride > ctx->capacity-ctx->fallback-ctx->warm_bytes-added) { return false; }
            added += stride;
            ctx->slots->protect(b->identity+":"+std::to_string(e));
            ctx->matched_hot.insert(b->hot_key+":"+std::to_string(e));
        }
    }
    std::lock_guard<std::mutex> lock(registry_mutex);
    if (registry.count(t)) { return false; }
    registry.emplace(t,b); ctx->tensors.push_back(t); ctx->warm_bytes += added;
    registered_bindings.store(registry.size(),std::memory_order_release);
    return true;
#else
    (void)ctx; (void)t; (void)fd; (void)offset; return false;
#endif
}

int ggml_cpu_expert_acquire(const struct ggml_tensor * t, int expert, struct ggml_cpu_expert_view * view) {
    *view = {};
    if (!registered_bindings.load(std::memory_order_acquire)) { return 0; }
    std::shared_ptr<binding> b;
    { std::lock_guard<std::mutex> lock(registry_mutex); auto found = registry.find(t); if (found == registry.end()) { return 0; } b = found->second; }
    try {
        if (expert < 0 || expert >= t->ne[2]) { throw std::runtime_error("expert ID outside admitted tensor"); }
        const std::string key = b->identity+":"+std::to_string(expert);
        auto l = b->slots->acquire(key,b->stride,[&](void * out,size_t bytes) {
#ifndef _WIN32
            const uint64_t start = b->offset+(uint64_t)expert*b->stride;
            size_t done = 0;
            while (done < bytes) {
                const auto n = pread(b->fd,(char *)out+done,bytes-done,(off_t)(start+done));
                if (n < 0 && errno == EINTR) { continue; }
                if (n <= 0) { throw std::runtime_error("short or failed expert read"); }
                done += (size_t)n;
            }
#endif
        });
        if (!l.data()) { return 0; }
        auto * held = new token(b,std::move(l));
        view->data = held->lease.data(); view->generation = held->lease.generation(); view->lease = held;
        return 1;
    } catch (const std::exception & e) { fprintf(stderr,"expert_weights demand_failed=%s\n",e.what()); return -1; }
}
bool ggml_cpu_expert_validate(struct ggml_cpu_expert_context * ctx) { return ctx && !ctx->tensors.empty() && ctx->hot == ctx->matched_hot; }
void ggml_cpu_expert_release(struct ggml_cpu_expert_view * view) { delete static_cast<token *>(view->lease); *view = {}; }
void ggml_cpu_expert_destroy(struct ggml_cpu_expert_context * ctx) {
    if (!ctx) { return; }
    ctx->slots->cancel();
    { std::lock_guard<std::mutex> lock(registry_mutex); for (auto t:ctx->tensors) { registry.erase(t); } registered_bindings.store(registry.size(),std::memory_order_release); }
    const auto c = ctx->slots->snapshot();
    fprintf(stderr,"expert_weights final fills=%zu hits=%zu joined=%zu bypass=%zu failures=%zu reserved=%zu outstanding=%zu leases=%zu peak=%zu\n",
        c.fills,c.hits,c.joined,c.bypass,c.failures,c.reserved_bytes,c.outstanding_bytes,c.active_leases,c.peak_bytes);
    delete ctx;
}
