"""Bounded structural CUDA-to-CPU lowering.

Kernel arithmetic and control flow are retained from source. The generated C++20
runtime executes CUDA threads cooperatively, including shared memory, block
barriers and full-warp shuffles. This is a CPU reference execution backend; it
is neither a GPU compiler nor a validated Ascend implementation.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re


def sha256(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def strip_comments(text):
    return re.sub(r'//[^\n]*|/\*.*?\*/', '', text, flags=re.S)


def balanced(text, opening, left='{', right='}'):
    depth = 0
    state = 'code'
    i = opening
    while i < len(text):
        c = text[i]
        pair = text[i:i+2]
        if state == 'line':
            if c == '\n': state = 'code'
        elif state == 'block':
            if pair == '*/': state = 'code'; i += 1
        elif state in {'"', "'"}:
            if c == '\\': i += 1
            elif c == state: state = 'code'
        elif pair == '//': state = 'line'; i += 1
        elif pair == '/*': state = 'block'; i += 1
        elif c in {'"', "'"}: state = c
        elif c == left: depth += 1
        elif c == right:
            depth -= 1
            if not depth: return i
        i += 1
    raise ValueError('Unbalanced production source')


def _parameters(signature):
    result = []
    for declaration in signature.split(','):
        declaration = re.sub(r'\b__restrict__\b', '', declaration).strip()
        match = re.fullmatch(r'(.+?[\s*])(\w+)', declaration)
        if match is None: raise ValueError('Unsupported kernel parameter declaration: ' + declaration)
        kind = re.sub(r'\s+', ' ', match[1]).strip()
        base = kind.replace('const ', '').replace('*', '').strip()
        if base not in {'float', 'double', 'int', 'int64_t', 'long long', 'size_t', 'unsigned', 'unsigned int'}:
            raise ValueError('Unsupported kernel parameter type: ' + kind)
        result.append({'name': match[2], 'type': kind, 'base': base,
                       'pointer': '*' in kind, 'const': bool(re.search(r'\bconst\b', kind))})
    return result


def _operation(params, body):
    pointers = [p for p in params if p['pointer']]
    scalars = [p for p in params if not p['pointer']]
    readable = [p for p in pointers if p['const']]
    writable = [p for p in pointers if not p['const']]
    if (len(params) == 6 and [p['base'] for p in pointers] == ['float', 'int', 'float']
            and len(readable) == 1 and len(scalars) == 3 and 'exp(' in body and '__shfl_' in body):
        return 'router', 'routing'
    if (len(params) == 7 and len(readable) == 3 and len(writable) == 1
            and len(scalars) == 3 and all(p['base'] == 'float' for p in pointers)):
        return 'moe_combine', 'aggregation'
    if (len(params) == 4 and len(readable) == 2 and len(writable) == 1
            and len(scalars) == 1 and re.search(r'\bexpf?\s*\(', body)):
        return 'swiglu', 'activation'
    if (len(params) == 5 and len(readable) == 1 and len(writable) == 1
            and len(scalars) == 3 and 'rsqrtf' in body and '__shfl_' in body):
        return 'rms_norm', 'normalization'
    integers = [p for p in scalars if p['base'] in {'int', 'int64_t', 'long long', 'size_t', 'unsigned', 'unsigned int'}]
    if (pointers and len(writable) == 1 and len(integers) == 1
            and all(p['base'] == 'float' for p in pointers) and 'threadIdx.x' in body
            and 'blockIdx.x' in body):
        return 'elementwise', 'elementwise'
    raise ValueError('Kernel signature has no executable tensor contract in this bounded compiler')


MATH_CALLS = {'exp', 'expf', 'fmax', 'fmaxf', 'fmin', 'fminf', 'sqrt', 'sqrtf', 'rsqrtf',
              'fabs', 'fabsf', 'tanh', 'tanhf', 'pow', 'powf', 'log', 'logf', 'sin', 'sinf',
              'cos', 'cosf', 'isfinite', 'size_t', 'int', 'float', 'double', 'int64_t',
              'for', 'if', 'while', 'switch', 'sizeof', 'static_cast', 'reinterpret_cast'}
COLLECTIVES = {'__syncthreads', '__shfl_down_sync', '__shfl_xor_sync', '__shfl_sync'}


def _check_supported(body):
    clean = strip_comments(body)
    if re.search(r'\b(?:threadIdx|blockIdx|blockDim|gridDim)\.[yz]\b',clean):raise ValueError('Multidimensional CUDA launch requires a declared multidimensional tensor contract')
    unknown_cuda = set(re.findall(r'\b(__\w+)\b', clean)) - COLLECTIVES - {'__shared__', '__restrict__'}
    if unknown_cuda: raise ValueError('Unsupported CUDA construct: ' + ', '.join(sorted(unknown_cuda)))
    if re.search(r'\b(?:atomic\w*|float[234]|half\d*|__half|uint[234]|int[234])\b', clean):
        raise ValueError('Unsupported atomic/vector/half operation')
    calls = set(re.findall(r'(?<![\w])([A-Za-z_]\w*)\s*\(', clean))
    unknown = calls - MATH_CALLS - COLLECTIVES
    if unknown: raise ValueError('Unresolved device helper or unsupported call: ' + ', '.join(sorted(unknown)))
    if re.search(r'#\s*(?:if|elif|else|define|include)', clean):
        raise ValueError('Conditional preprocessor inside kernel requires preprocessing before lowering')
    return {'barrier': '__syncthreads' in clean, 'shuffle': '__shfl_' in clean,
            'shared': '__shared__' in clean, 'thread_index': 'threadIdx.' in clean,
            'block_index': 'blockIdx.' in clean,
            'collectives': sorted(calls & COLLECTIVES)}


def _constants(text, body):
    definitions = {}
    for match in re.finditer(r'\bconstexpr\s+((?:unsigned\s+)?(?:int|float|double|size_t))\s+(\w+)\s*=\s*([^;]+);', strip_comments(text)):
        if re.search(r'\b' + re.escape(match[2]) + r'\b', body) and not re.search(r'\b(?:const|constexpr)\s+[^;]*\b' + re.escape(match[2]) + r'\s*=', body):
            if re.search(r'[^\w\s.+*/()<>|&~-]', match[3]): raise ValueError('Unsupported file constant expression')
            definitions[match[2]] = 'constexpr ' + match[1] + ' ' + match[2] + ' = ' + match[3] + ';'
    return list(definitions.values())


def _source_guards(text, offset):
    stack=[]
    for line in text[:offset].splitlines():
        m=re.match(r'\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)',line)
        if not m:continue
        if m[1] in {'if','ifdef','ifndef'}:stack.append(m[0].strip())
        elif m[1]=='endif':
            if stack:stack.pop()
        elif stack:stack[-1]=m[0].strip()
    return stack


def _tensor_extents(params, operation):
    names=[p['name'] for p in params]
    if operation=='router':return {names[0]:names[1]+'*'+names[2],names[4]:names[1]+'*'+names[3],names[5]:names[1]+'*'+names[3]}
    if operation=='swiglu':return {names[i]:names[3] for i in range(3)}
    if operation=='moe_combine':return {names[0]:names[4]+'*'+names[5],names[1]:names[5],names[2]:names[4],names[3]:names[4]}
    if operation=='rms_norm':return {names[0]:names[2]+'*'+names[3],names[1]:names[3]}
    dimension=next(p['name'] for p in params if not p['pointer'] and p['base'] not in {'float','double'})
    return {p['name']:dimension for p in params if p['pointer']}


def discover_operations(repository):
    """Discover actual production kernels by signature/body, independent of names."""
    root = Path(repository).resolve(strict=True)
    descriptors = []
    pattern = re.compile(r'__global__\s+(?:__launch_bounds__\([^)]*\)\s+)?void\s+(?:__launch_bounds__\([^)]*\)\s+)?(\w+)\s*\(')
    for path in sorted((root/'src').rglob('*.cu')):
        text = path.read_text(encoding='utf-8-sig')
        for match in pattern.finditer(text):
            try:
                parameter_open = text.index('(', match.start() + len('__global__'))
                # __launch_bounds__ may precede the actual name.
                parameter_open = text.index('(', match.start(1) + len(match[1]))
                close = balanced(text, parameter_open, '(', ')')
                opening = text.index('{', close)
                if ';' in text[close+1:opening]: continue
                closing = balanced(text, opening)
                body = text[opening+1:closing]
                source = text[match.start():closing+1]
                relative = path.relative_to(root).as_posix()
                descriptor = {'id': relative + ':' + match[1], 'name': match[1], 'function': match[1],
                    'sourcefile': relative, 'path': relative, 'line': text[:match.start()].count('\n')+1,
                    'end_line': text[:closing].count('\n')+1, 'source_sha256': sha256(path.read_bytes()),
                    'function_sha256': sha256(source), 'source_code': source, 'body': body,
                    'source_path': str(path), 'parameters_text': text[parameter_open+1:close], 'signature':text[match.start():opening].strip(), 'build_guards':_source_guards(text,match.start())}
                try:
                    params = _parameters(descriptor['parameters_text'])
                    if descriptor['build_guards']:raise ValueError('Conditionally compiled kernel requires an explicit preprocessed source configuration: '+', '.join(descriptor['build_guards']))
                    operation, category = _operation(params, strip_comments(body))
                    features = _check_supported(body)
                    features.update(has_softmax=bool(re.search(r'\bexp\s*\(',strip_comments(body))), configurable_experts=operation=='router', configurable_k=operation in {'router','moe_combine'}, stable_index_tie=bool(re.search(r'==\s*\w+\s*&&[^;]+<',strip_comments(body))))
                    # Unbound template symbols are not silently replaced by chosen constants.
                    before = text[max(0, match.start()-100):match.start()]
                    if re.search(r'template\s*<[^>]*>\s*$', before):
                        raise ValueError('Templated kernel needs an explicit template instantiation contract')
                    descriptor.update(parameters=params, params=params, tensor_extents=_tensor_extents(params,operation), operation=operation, category=category,
                        features=features, lowering_kind='cooperative' if any(features[k] for k in ['barrier','shuffle','shared']) else 'scalar',
                        constants=_constants(text, strip_comments(body)), supported=True)
                except ValueError as error:
                    descriptor.update(supported=False, reason=str(error), operation='unsupported', category='unsupported',
                                      features={}, lowering_kind='unsupported')
                descriptors.append(descriptor)
            except (ValueError, IndexError):
                continue
    return descriptors


def lower_operation(repository, descriptor):
    """Bind a discovered function to its live source and lower its real body."""
    repository = Path(repository).resolve(strict=True)
    matches = [value for value in discover_operations(repository) if value['id'] == descriptor['id']]
    if len(matches) != 1: raise ValueError('Discovered source function no longer exists')
    actual = matches[0]
    for key in ['source_sha256','function_sha256','source_code','parameters_text']:
        if descriptor.get(key) != actual.get(key): raise ValueError('Actual source/slice changed: ' + key)
    if not actual['supported']: raise ValueError(actual['reason'])
    body = strip_comments(actual['body'])
    # These are syntax/execution-primitive transformations. Arithmetic statements,
    # loops, comparisons and selection writes are taken from the actual source.
    dynamic = re.compile(r'extern\s+__shared__\s+([\w: ]+?)\s+(\w+)\s*\[\s*\]\s*;')
    body = dynamic.sub(lambda m: 'auto* '+m[2]+' = block.dynamic_shared<'+m[1].strip()+'>();', body)
    shared = re.compile(r'__shared__\s+([\w: ]+?)\s+(\w+)\s*(?:\[([^;]+?)\])?\s*;')
    def shared_declaration(match):
        kind, name, length = match[1].strip(), match[2], match[3]
        return ('auto* ' + name + ' = block.shared<' + kind + '>("'+name+'", '+length+');') if length else ('auto& '+name+' = *block.shared<'+kind+'>("'+name+'", 1);')
    body = shared.sub(shared_declaration, body)
    collective_site=0
    def barrier_site(match):
        nonlocal collective_site
        collective_site+=1
        return 'co_await thread.barrier('+str(collective_site)+')'
    body = re.sub(r'__syncthreads\s*\(\s*\)', barrier_site, body)
    for name, target in [('__shfl_down_sync','shuffle_down'),('__shfl_xor_sync','shuffle_xor'),('__shfl_sync','shuffle_index')]:
        # Parentheses around co_await preserve its precedence in compound arithmetic.
        while True:
            match = re.search(r'\b'+name+r'\s*\(', body)
            if not match: break
            opening = body.index('(', match.start()); closing = balanced(body, opening, '(', ')')
            args = body[opening+1:closing]
            collective_site+=1
            body = body[:match.start()] + '(co_await thread.'+target+'('+str(collective_site)+','+args+'))' + body[closing+1:]
    body = re.sub(r'\breturn\s*;', 'co_return;', body)
    body = re.sub(r'^\s*#pragma\s+unroll[^\n]*', '', body, flags=re.M)
    body = re.sub(r'\b__restrict__\b', '', body)
    # Global pointers become checked views with contract-derived extents. Local
    # aliases of those views retain bounds instead of silently escaping to raw
    # host memory. Shared-memory casts remain source-native within block storage.
    aliases=set(actual['tensor_extents'])
    alias_pattern=re.compile(r'(?:const\s+)?(?:float|double|int)\s*\*\s*(\w+)\s*=\s*(\w+)\b([^;]*);')
    changed=True
    while changed:
        changed=False
        def alias(match):
            nonlocal changed
            if match[2] in aliases:
                aliases.add(match[1]);changed=True
                return 'auto '+match[1]+' = '+match[2]+match[3]+';'
            return match[0]
        body=alias_pattern.sub(alias,body)
    params = ', '.join(('cuda_cpu::Span<'+('const ' if p['const'] else '')+p['base']+'>' if p['pointer'] else p['type'])+' '+p['name'] for p in actual['parameters'])
    symbol = 'kernel_' + sha256(actual['id'])[:16]
    preamble = '\n'.join(actual['constants'])
    lowered = 'namespace '+symbol+'_scope {\n'+preamble + '\nstatic cuda_cpu::Task '+symbol+'('+params+', cuda_cpu::Block& block, cuda_cpu::Thread& thread) {\n'
    lowered += '    const auto threadIdx = thread.index(); const auto blockIdx = block.index();\n    const auto blockDim = block.dimensions(); const auto gridDim = block.grid(); const int warpSize = 32;\n'
    lowered += body + '\n    co_return;\n}\n}\n'
    actual['semantic_ir'] = {'operation': actual['operation'], 'category':actual['category'], 'lowering':'cuda_cooperative_cpu_v1',
        'lowering_kind':actual['lowering_kind'], 'features':actual['features'], 'parameters':actual['parameters'],
        'tensor_extents':actual['tensor_extents'], 'symbol':symbol+'_scope::'+symbol, 'lowered_cpp':lowered, 'transformed_body':body, 'scalar_body':body,
        'launch': {'threads':32,'blocks':'contract-derived','dynamic_shared_bytes':65536},
        'precision':'Source expressions, casts, local types and reduction order retained; CPU math intrinsics; no GPU bit-equivalence claim'}
    return actual


CPU_RUNTIME = r'''#pragma once
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
'''
