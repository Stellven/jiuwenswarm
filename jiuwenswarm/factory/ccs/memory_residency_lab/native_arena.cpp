#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <set>
#include <vector>
struct T {size_t n,off; int begin,end;};
int main(){size_t n,bytes;if(!(std::cin>>n>>bytes)||n<1||n>128||bytes>268435456)return 2;
 std::vector<T> ts(n);std::set<int> events;
 for(auto &t:ts){if(!(std::cin>>t.n>>t.begin>>t.end>>t.off)||!t.n||t.begin<0||t.end<=t.begin||t.off>bytes||t.n>bytes-t.off)return 2;events.insert(t.begin);events.insert(t.end);}
 for(size_t i=0;i<n;i++)for(size_t j=i+1;j<n;j++)if(ts[i].begin<ts[j].end&&ts[j].begin<ts[i].end&&ts[i].off<ts[j].off+ts[j].n&&ts[j].off<ts[i].off+ts[i].n)return 3;
 uint64_t baseline_bytes=0,baseline_checksum=0;double baseline_ms=0;{auto start=std::chrono::steady_clock::now();std::vector<std::vector<uint8_t>> independent;for(size_t i=0;i<n;i++){independent.emplace_back(ts[i].n,uint8_t(i+1));baseline_bytes+=independent.back().size();}for(auto &v:independent)for(auto x:v)baseline_checksum+=x;baseline_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();}
 auto start=std::chrono::steady_clock::now();std::vector<uint8_t> arena(bytes);uint64_t checked=0,written=0;std::vector<bool> active(n,false);
 for(int step:events){for(size_t i=0;i<n;i++)if(active[i]){auto&t=ts[i];for(size_t b=0;b<t.n;b++)if(arena[t.off+b]!=uint8_t(i+1))return 4;checked+=t.n;if(t.end==step)active[i]=false;}
 for(size_t i=0;i<n;i++)if(ts[i].begin==step){auto&t=ts[i];std::fill(arena.begin()+t.off,arena.begin()+t.off+t.n,uint8_t(i+1));written+=t.n;active[i]=true;}}
 double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
 std::cout<<"{\"correct\":true,\"arena_allocated_bytes\":"<<arena.size()<<",\"baseline_independent_payload_bytes\":"<<baseline_bytes<<",\"baseline_allocate_touch_check_ms\":"<<baseline_ms<<",\"baseline_checksum\":"<<baseline_checksum<<",\"checked_bytes\":"<<checked<<",\"written_bytes\":"<<written<<",\"allocation_touch_check_ms\":"<<ms<<"}\n";}
