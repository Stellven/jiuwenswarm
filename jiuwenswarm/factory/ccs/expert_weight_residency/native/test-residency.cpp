#include "expert-residency.hpp"
#include <cassert>
#include <cstring>
#include <future>
#include <thread>
#include <iostream>
using expert_weight::cache;
int main() {
    cache c(8,8,2);
    auto fill = [](void * p,size_t n) { memset(p,7,n); };
    auto a = c.acquire("a",8,fill); const auto generation=a.generation();
    assert(a.data() && c.snapshot().active_leases==1);
    assert(!c.acquire("b",8,fill).data());
    a.release();
    auto b=c.acquire("b",8,fill); assert(b.generation()!=generation); b.release();
    assert(!c.acquire("oversize",9,fill).data());
    assert(c.snapshot().peak_bytes<=8);
    cache joined(8,8,2);
    std::promise<void> started, finish;
    auto gate=finish.get_future().share();
    auto first=std::async(std::launch::async,[&] { return joined.acquire("same",8,[&](void * p,size_t n) { started.set_value(); gate.wait(); fill(p,n); }); });
    started.get_future().wait();
    auto second=std::async(std::launch::async,[&] { return joined.acquire("same",8,[](void *,size_t) { assert(false); }); });
    while (joined.snapshot().joined==0) { std::this_thread::yield(); }
    assert(joined.snapshot().outstanding_bytes==8);
    finish.set_value();
    auto one=first.get(); auto two=second.get();
    assert(one.data()==two.data() && one.generation()==two.generation());
    one.release(); assert(!joined.acquire("other",8,fill).data()); two.release();
    assert(joined.snapshot().fills==1 && joined.snapshot().active_leases==0);
    cache failed(8,8,2);
    try { failed.acquire("short",8,[](void *,size_t) { throw std::runtime_error("short read"); }); assert(false); } catch (const std::runtime_error &) {}
    assert(failed.snapshot().reserved_bytes==0 && failed.snapshot().outstanding_bytes==0);
    auto retry=failed.acquire("short",8,fill); assert(retry.data()); retry.release();
    cache cancelled(8,8,2); std::promise<void> filling, unblock; auto wait=unblock.get_future().share();
    auto pending=std::async(std::launch::async,[&] {
        try { cancelled.acquire("pending",8,[&](void *,size_t) { filling.set_value(); wait.wait(); }); return false; }
        catch (const std::runtime_error &) { return true; }
    });
    filling.get_future().wait(); cancelled.cancel(); unblock.set_value(); assert(pending.get());
    assert(cancelled.snapshot().outstanding_bytes==0 && cancelled.snapshot().reserved_bytes==0);
    cache hot(16,8,2,{"warm"}); auto warm=hot.acquire("warm",8,fill); warm.release();
    auto cold=hot.acquire("cold",8,fill); cold.release(); auto newer=hot.acquire("new",8,fill); newer.release();
    auto kept=hot.acquire("warm",8,[](void *,size_t) { assert(false); }); kept.release();
    std::cout << "PASS budget, lease generation, held eviction, coalescing, failed fill, cancellation, static warm set\n";
}
