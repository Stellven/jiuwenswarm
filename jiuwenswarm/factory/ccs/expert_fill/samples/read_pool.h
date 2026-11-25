// SAMPLE (starting point, not the change): a fixed pool of pread workers and the address -> file lookup.
// Linux only. Adapt names, error handling and placement to the tree in front of you; see METHOD.md step 4.
//
// Why pread into a scratch buffer: a buffered read populates the page cache, so the expert matmul that follows
// takes minor faults on the shared file mapping. Reading into the tensor's own memory would need a writable or
// private mapping and changes what the kernel reads; never do that (verify: no_tensor_writes).
#pragma once
#include <algorithm>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

struct read_task { int fd; uint64_t off; size_t len; };

class read_pool {
public:
    read_pool(int n, size_t chunk) : chunk(chunk) {
        for (int i = 0; i < n; ++i) workers.emplace_back([this] { work(); });
    }
    ~read_pool() {
        { std::lock_guard<std::mutex> lk(m); stop = true; }
        cv.notify_all();
        for (auto & w : workers) w.join();
    }
    // blocks until every task is read; tasks are taken under the lock (a 1 MiB pread dwarfs the lock cost)
    void run(std::vector<read_task> todo) {
        { std::lock_guard<std::mutex> lk(m); tasks = std::move(todo); next = 0; pending = tasks.size(); }
        cv.notify_all();
        std::unique_lock<std::mutex> lk(m);
        done.wait(lk, [this] { return pending == 0; });
        tasks.clear();
    }
    uint64_t bytes = 0, reads = 0, errors = 0;   // updated under m
private:
    size_t chunk;
    std::mutex m;
    std::condition_variable cv, done;
    std::vector<read_task> tasks;
    size_t next = 0, pending = 0;
    bool stop = false;
    std::vector<std::thread> workers;
    void work() {
        std::vector<uint8_t> buf(chunk);
        for (;;) {
            read_task t;
            {
                std::unique_lock<std::mutex> lk(m);
                cv.wait(lk, [this] { return stop || next < tasks.size(); });
                if (stop) return;
                t = tasks[next++];
            }
            uint64_t got = 0, n = 0, e = 0;
            while (got < t.len) {
                ssize_t r = pread(t.fd, buf.data(), std::min(buf.size(), (size_t) (t.len - got)), (off_t) (t.off + got));
                n++;
                if (r <= 0) { e++; break; }
                got += (uint64_t) r;
            }
            std::lock_guard<std::mutex> lk(m);
            bytes += got; reads += n; errors += e;
            if (--pending == 0) done.notify_all();
        }
    }
};

// address -> (path, file offset) from /proc/self/maps. llama.cpp maps each GGUF whole at offset 0, so
// file_off = addr - start + pgoff. Re-read the maps when a lookup misses (mappings change after load).
struct map_region { uintptr_t start, end; uint64_t pgoff; std::string path; };

static std::vector<map_region> read_maps() {
    std::vector<map_region> out;
    FILE * f = std::fopen("/proc/self/maps", "r");
    if (!f) return out;
    char line[4096];
    while (std::fgets(line, sizeof(line), f)) {
        unsigned long long s, e, off; char perms[8]; int n = 0;
        if (std::sscanf(line, "%llx-%llx %7s %llx %*s %*s %n", &s, &e, perms, &off, &n) < 4 || n <= 0) continue;
        std::string path(line + n);
        while (!path.empty() && (path.back() == '\n' || path.back() == ' ')) path.pop_back();
        if (!path.empty() && path[0] == '/') out.push_back({ (uintptr_t) s, (uintptr_t) e, (uint64_t) off, path });
    }
    std::fclose(f);
    return out;
}

// non-resident page runs of [addr, addr+len): mincore on the page-aligned span
static std::vector<std::pair<uintptr_t, size_t>> missing_runs(const void * addr, size_t len) {
    const size_t pg = (size_t) sysconf(_SC_PAGESIZE);
    const uintptr_t a = (uintptr_t) addr & ~(uintptr_t) (pg - 1);
    const uintptr_t b = ((uintptr_t) addr + len + pg - 1) & ~(uintptr_t) (pg - 1);
    std::vector<unsigned char> v((b - a) / pg, 0);
    std::vector<std::pair<uintptr_t, size_t>> runs;
    if (mincore((void *) a, b - a, v.data()) != 0) { runs.push_back({ a, b - a }); return runs; }
    for (size_t p = 0; p < v.size(); ) {
        if (v[p] & 1) { p++; continue; }
        size_t q = p;
        while (q < v.size() && !(v[q] & 1)) q++;
        runs.push_back({ a + p*pg, (q - p)*pg });
        p = q;
    }
    return runs;
}
