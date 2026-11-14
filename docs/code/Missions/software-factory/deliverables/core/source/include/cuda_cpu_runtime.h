#pragma once
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <coroutine>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <exception>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <type_traits>
#include <vector>
inline float rsqrtf(float value) { return 1.0f / std::sqrt(value); }
namespace cuda_cpu {
template<class T> struct Span {
 T* data;std::size_t size;
 T& operator[](std::int64_t index)const{if(!data||index<0||std::uint64_t(index)>=size)throw std::runtime_error("source tensor access exceeds declared contract extent");return data[index];}
 Span operator+(std::size_t offset)const{if(offset>size)throw std::runtime_error("source pointer offset exceeds tensor extent");return {data?data+offset:nullptr,size-offset};}
 Span& operator+=(std::size_t offset){*this=*this+offset;return *this;}
 explicit operator bool()const{return data!=nullptr;}
};
template<class T> Span<T> view(T* data,std::size_t size){return {data,size};}
struct Dim3 { unsigned x=1,y=1,z=1; };
struct Task {
 struct promise_type {
  std::exception_ptr error;
  Task get_return_object(){return Task{std::coroutine_handle<promise_type>::from_promise(*this)};}
  std::suspend_always initial_suspend() noexcept{return {};}
  std::suspend_always final_suspend() noexcept{return {};}
  void return_void() noexcept{}
  void unhandled_exception(){error=std::current_exception();}
 };
 std::coroutine_handle<promise_type> handle;
 explicit Task(std::coroutine_handle<promise_type> h):handle(h){}
 Task(Task&& other) noexcept:handle(std::exchange(other.handle,{})){}
 Task(const Task&)=delete;
 ~Task(){if(handle)handle.destroy();}
};
enum class Wait { Ready, Barrier, Shuffle, Done };
enum class Shuffle { Down, Xor, Index };
struct Block;
struct Thread {
 Block* owner; unsigned lane;
 Wait wait=Wait::Ready; unsigned epoch=0,sequence=0,site=0;int value_type=0;
 Shuffle operation=Shuffle::Down; int argument=0,width=32; unsigned mask=0xffffffffu;
 std::uint64_t value=0,result=0;
 Dim3 index() const{return {lane,0,0};}
 struct Barrier {
  Thread& thread;unsigned site;
  bool await_ready() const noexcept{return false;}
  void await_suspend(std::coroutine_handle<>) const {thread.wait=Wait::Barrier;thread.epoch++;thread.site=site;}
  void await_resume() const noexcept{}
 };
 Barrier barrier(unsigned site){return {*this,site};}
 template<class T> struct Exchange {
  Thread& thread; T input; Shuffle operation; unsigned site,mask; int argument,width;
  bool await_ready() const noexcept{return false;}
  void await_suspend(std::coroutine_handle<>) {
   static_assert(sizeof(T)<=sizeof(std::uint64_t));
   if(mask!=0xffffffffu || width<1 || width>32 || (width&(width-1)))
    throw std::runtime_error("unsupported CUDA shuffle mask/width; no invented partial-warp semantics");
   thread.value=0;std::memcpy(&thread.value,&input,sizeof(T));thread.mask=mask;
   thread.operation=operation;thread.argument=argument;thread.width=width;
   thread.sequence++;thread.site=site;thread.value_type=int(sizeof(T))*4+int(std::is_floating_point_v<T>)*2+int(std::is_signed_v<T>);thread.wait=Wait::Shuffle;
  }
  T await_resume() const {T output;std::memcpy(&output,&thread.result,sizeof(T));return output;}
 };
 template<class T> Exchange<T> shuffle_down(unsigned site,unsigned mask,T value,int delta,int width=32){return {*this,value,Shuffle::Down,site,mask,delta,width};}
 template<class T> Exchange<T> shuffle_xor(unsigned site,unsigned mask,T value,int lane_mask,int width=32){return {*this,value,Shuffle::Xor,site,mask,lane_mask,width};}
 template<class T> Exchange<T> shuffle_index(unsigned site,unsigned mask,T value,int source,int width=32){return {*this,value,Shuffle::Index,site,mask,source,width};}
};
struct Buffer {
 std::vector<std::max_align_t> storage;std::size_t bytes;
 explicit Buffer(std::size_t count):storage((count+sizeof(std::max_align_t)-1)/sizeof(std::max_align_t)),bytes(count){}
 void* data(){return storage.data();}
};
struct Block {
 unsigned block_index,grid_size;std::map<std::string,std::unique_ptr<Buffer>> shared_storage;
 Buffer dynamic{65536};
 Dim3 index() const{return {block_index,0,0};}
 Dim3 dimensions() const{return {32,1,1};}
 Dim3 grid() const{return {grid_size,1,1};}
 template<class T>T* dynamic_shared(){return static_cast<T*>(dynamic.data());}
 template<class T>T* shared(const std::string& name,std::size_t count){
  if(count>65536/sizeof(T))throw std::runtime_error("shared allocation exceeds bounded CPU kernel capacity");
  auto found=shared_storage.find(name);const auto bytes=count*sizeof(T);
  if(found==shared_storage.end())found=shared_storage.emplace(name,std::make_unique<Buffer>(bytes)).first;
  if(found->second->bytes!=bytes)throw std::runtime_error("non-uniform shared declaration");
  return static_cast<T*>(found->second->data());
 }
};
template<class Factory> void launch(unsigned grid_size,Factory factory) {
 if(grid_size>1000000)throw std::runtime_error("invalid CPU kernel launch extent");
 for(unsigned b=0;b<grid_size;++b) {
  Block block{b,grid_size};std::vector<Thread> threads;std::vector<Task> tasks;
  threads.reserve(32);tasks.reserve(32);
  for(unsigned lane=0;lane<32;++lane)threads.push_back(Thread{&block,lane});
  for(unsigned lane=0;lane<32;++lane)tasks.push_back(factory(block,threads[lane]));
  std::size_t rounds=0;
  for(;;){
   if(++rounds>10000000)throw std::runtime_error("CPU cooperative kernel instruction budget exceeded");
   bool progress=false;unsigned done=0;
   for(unsigned lane=0;lane<32;++lane){
    if(threads[lane].wait==Wait::Ready){
     tasks[lane].handle.resume();progress=true;
     if(tasks[lane].handle.promise().error)std::rethrow_exception(tasks[lane].handle.promise().error);
     if(tasks[lane].handle.done())threads[lane].wait=Wait::Done;
    }
    if(threads[lane].wait==Wait::Done)done++;
   }
   if(done==32)break;
   bool barrier=true,shuffle=true;
   const auto epoch=threads[0].epoch,sequence=threads[0].sequence;
   for(const auto& thread:threads){
    barrier=barrier && thread.wait==Wait::Barrier && thread.epoch==epoch && thread.site==threads[0].site;
    shuffle=shuffle && thread.wait==Wait::Shuffle && thread.sequence==sequence && thread.operation==threads[0].operation && thread.site==threads[0].site && thread.value_type==threads[0].value_type;
   }
   if(barrier){for(auto& thread:threads)thread.wait=Wait::Ready;progress=true;}
   if(shuffle){
    for(auto& thread:threads){
     const int lane=int(thread.lane),base=(lane/thread.width)*thread.width;int source=lane;
     if(thread.operation==Shuffle::Down){const int candidate=lane+thread.argument;if(candidate<base+thread.width)source=candidate;}
     else if(thread.operation==Shuffle::Xor){const int candidate=lane^thread.argument;if(candidate>=base&&candidate<base+thread.width)source=candidate;}
     else source=base+(thread.argument&(thread.width-1));
     if(source<0||source>=32)throw std::runtime_error("invalid shuffle source");
     thread.result=threads[unsigned(source)].value;
    }
    for(auto& thread:threads)thread.wait=Wait::Ready;progress=true;
   }
   if(!progress)throw std::runtime_error("divergent/unsupported CUDA collective execution; CPU lowering aborted");
  }
 }
}
}
