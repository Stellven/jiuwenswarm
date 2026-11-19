#include "ggml.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "ggml-cpu-expert.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <string>
#include <exception>
#include <unistd.h>

static void configure(size_t cap) {
    setenv("LLAMA_EXPERT_RESIDENCY","1",1); setenv("LLAMA_EXPERT_STREAMING","1",1);
    for (auto name:{"LLAMA_EXPERT_FIXED_BYTES","LLAMA_EXPERT_SEQUENCE_BYTES","LLAMA_EXPERT_WORKSPACE_BYTES","LLAMA_EXPERT_HEADROOM_BYTES"}) { setenv(name,"0",1); }
    for (auto name:{"LLAMA_EXPERT_PHYSICAL_BYTES","LLAMA_EXPERT_SLOT_BYTES","LLAMA_EXPERT_IO_BYTES","LLAMA_EXPERT_FALLBACK_BYTES"}) { setenv(name,std::to_string(cap).c_str(),1); }
    setenv("LLAMA_EXPERT_CHECKPOINT",std::string(64,'a').c_str(),1);
}
int main(int argc,char ** argv) {
    const bool quant=argc>1; const int k=quant?256:4, rows=quant?32:2, batch=quant?16:2;
    ggml_init_params p={16*1024*1024,nullptr,false}; auto * ctx=ggml_init(p); assert(ctx);
    auto type = !quant ? GGML_TYPE_F32 : strcmp(argv[1],"q4_k")==0 ? GGML_TYPE_Q4_K : strcmp(argv[1],"q5_0")==0 ? GGML_TYPE_Q5_0 : strcmp(argv[1],"q8_0")==0 ? GGML_TYPE_Q8_0 : strcmp(argv[1],"iq1_m")==0 ? GGML_TYPE_IQ1_M : strcmp(argv[1],"iq2_xs")==0 ? GGML_TYPE_IQ2_XS : GGML_TYPE_IQ2_XXS;
    auto * w=ggml_new_tensor_3d(ctx,type,k,rows,3);
    ggml_set_name(w,"blk.0.ffn_up_exps.weight");
    auto * x=ggml_new_tensor_3d(ctx,GGML_TYPE_F32,k,2,batch);
    auto * ids=ggml_new_tensor_2d(ctx,GGML_TYPE_I32,2,batch);
    auto * y=ggml_mul_mat_id(ctx,w,x,ids);
    std::vector<float> f(k*rows*3); for (size_t i=0;i<f.size();++i) { f[i]=std::sin(float(i)*.1f); }
    if (quant) { std::vector<float> imatrix(k,1.f); ggml_quantize_chunk(w->type,f.data(),w->data,0,rows*3,k,imatrix.data()); }
    else { memcpy(w->data,f.data(),f.size()*4); }
    for (int i=0;i<k*2*batch;++i) { ((float *)x->data)[i]=float(i%7-3)/8; }
    for (int i=0;i<batch;++i) { ((int32_t *)ids->data)[2*i]=2; ((int32_t *)ids->data)[2*i+1]=i%2; }
    auto * graph=ggml_new_graph(ctx); ggml_build_forward_expand(graph,y);
    assert(ggml_graph_compute_with_ctx(ctx,graph,4)==GGML_STATUS_SUCCESS);
    std::vector<uint8_t> original(ggml_nbytes(y)); memcpy(original.data(),y->data,original.size());
    FILE * file=tmpfile(); assert(file); const size_t prefix=64;
    std::vector<uint8_t> pad(prefix,0xa5); assert(fwrite(pad.data(),1,pad.size(),file)==pad.size());
    assert(fwrite(w->data,1,ggml_nbytes(w),file)==ggml_nbytes(w)); fflush(file);
    configure(w->nb[2]*3);
    setenv("LLAMA_EXPERT_STREAMING","0",1);
    try { ggml_cpu_expert_create(); assert(false); } catch (const std::exception &) {}
    setenv("LLAMA_EXPERT_STREAMING","1",1);
    setenv("LLAMA_EXPERT_WARM_SET","blk.0.ffn_up_exps.weight:999",1);
    auto * invalid=ggml_cpu_expert_create();
    assert(ggml_cpu_expert_register(invalid,w,fileno(file),prefix));
    assert(!ggml_cpu_expert_validate(invalid)); ggml_cpu_expert_destroy(invalid);
    unsetenv("LLAMA_EXPERT_WARM_SET");
    auto * cache=ggml_cpu_expert_create(); assert(cache);
    assert(ggml_cpu_expert_register(cache,w,fileno(file),prefix));
    assert(ggml_cpu_expert_validate(cache));
    ggml_cpu_expert_view view={}; assert(ggml_cpu_expert_acquire(w,2,&view)==1);
    assert(memcmp(view.data,(char *)w->data+2*w->nb[2],w->nb[2])==0); ggml_cpu_expert_release(&view);
    assert(ggml_graph_compute_with_ctx(ctx,graph,4)==GGML_STATUS_SUCCESS);
    assert(memcmp(original.data(),y->data,original.size())==0);
    ggml_cpu_expert_destroy(cache);
    // Same selected IDs and mixture order; disabling restores the original reader.
    setenv("LLAMA_EXPERT_RESIDENCY","0",1);setenv("LLAMA_EXPERT_STREAMING","0",1);
    assert(ggml_cpu_expert_create()==nullptr);
    assert(ggml_graph_compute_with_ctx(ctx,graph,4)==GGML_STATUS_SUCCESS);
    assert(memcmp(original.data(),y->data,original.size())==0);
    configure(w->nb[2]); cache=ggml_cpu_expert_create(); assert(ggml_cpu_expert_register(cache,w,fileno(file),prefix));
    // Hold the only slot while the real graph demands other experts: explicit mapped fallback.
    assert(ggml_cpu_expert_acquire(w,2,&view)==1);
    const auto held_generation=view.generation;
    assert(ggml_graph_compute_with_ctx(ctx,graph,4)==GGML_STATUS_SUCCESS);
    assert(memcmp(original.data(),y->data,original.size())==0);
    assert(view.generation==held_generation && memcmp(view.data,(char *)w->data+2*w->nb[2],w->nb[2])==0);
    ggml_cpu_expert_release(&view); ggml_cpu_expert_destroy(cache);
    cache=ggml_cpu_expert_create(); assert(ggml_cpu_expert_register(cache,w,fileno(file),prefix));
    assert(ftruncate(fileno(file),prefix+1)==0);
    assert(ggml_cpu_expert_acquire(w,0,&view)==-1);
    ggml_cpu_expert_destroy(cache); fclose(file); ggml_free(ctx);
    printf("PASS actual MUL_MAT_ID %s: byte fidelity, stock/candidate/off exact rows, short read failure\n",ggml_type_name(type));
}
