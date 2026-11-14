#include "strata/kernels/ascend/expert_adapter.hpp"
#include "strata/kernels/cpu/expert_layout.hpp"
#include "strata/kernels/cpu/pool.hpp"
#include <iostream>
#include <random>
#include <cstring>

namespace cpu = strata::kernels::cpu;
namespace port = strata::kernels::ascend;
// Test-only CPU executor for the representation transformation. It is never a
// fallback selected by the production Ascend dispatch, and does not prove NPU parity.
struct ReferenceOps {
    void matvec(const float* w, int rows, int cols, const float* x, float* y) {
        for (int r = 0; r < rows; ++r) { float sum = 0; for (int c = 0; c < cols; ++c) sum += w[size_t(r)*cols+c]*x[c]; y[r]=sum; }
    }
    void swiglu(const float* g,const float* u,int n,float* y) {
        for(int i=0;i<n;++i)y[i]=(g[i]/(1.f+std::exp(-g[i])))*u[i];
    }
};
int main() {
    if (!cpu::cpu_avx2_ok()) { std::cerr << "SKIP: host quantizer requires AVX2\n"; return 77; }
    std::mt19937 random(20261113);
    std::vector<uint8_t> blob(cpu::BLOB);
    for (size_t i=0;i<cpu::O_GU_SCALES;++i) blob[i]=uint8_t(random());
    // Nonconstant fp16 scales exercise gate/up interleaving and both weight/activation block sizes.
    for (size_t i=cpu::O_GU_SCALES;i<blob.size();i+=2) { uint16_t scale=uint16_t(0x1800+(random()%0x600)); std::memcpy(blob.data()+i,&scale,2); }
    std::vector<float> x(cpu::H), expected(cpu::H), actual(cpu::H); ReferenceOps ops;
    double largest = 0;
    for (int trial=0;trial<4;++trial) {
        for (auto& value:x) value=float(int(random()%2001)-1000)/317.f;
        cpu::ActQ quantized; cpu::act_quant_q8_1(x.data(),cpu::H,quantized);
        cpu::s2_expert_scalar(blob.data(),x.data(),expected.data(),true);
        port::expert_q2(blob.data(),quantized,actual.data(),ops);
        for(int i=0;i<cpu::H;++i) { double error=std::abs(double(actual[i])-expected[i]); largest=std::max(largest,error); if(error>1e-6+1e-5*std::abs(expected[i])) {std::cerr<<"projection conversion mismatch\n";return 1;} }
    }
    cpu::ActQ invalid{}; float values[cpu::H]; bool rejected=false;
    try { port::activation_values(invalid,cpu::H,values); } catch(const std::runtime_error&) {rejected=true;}
    if(!rejected) return 2;
    if (!port::compiled()) {
        cpu::ExpertPool pool(1, false, true); cpu::ActQ activation;
        cpu::act_quant_q8_1(x.data(),cpu::H,activation);
        std::fill(actual.begin(),actual.end(),-12345.f);
        cpu::ExpertJob job; job.blob=blob.data(); job.act=&activation; job.out=actual.data();
#if defined(_WIN32)
        _putenv_s("STRATA_EXPERT_BACKEND","ascend");
#else
        setenv("STRATA_EXPERT_BACKEND","ascend",1);
#endif
        bool refused=false;
        try { pool.run(&job,1); } catch(const std::runtime_error& error) { refused=std::string(error.what()).find("no CPU/GPU fallback")!=std::string::npos; }
#if defined(_WIN32)
        _putenv_s("STRATA_EXPERT_BACKEND","");
#else
        unsetenv("STRATA_EXPERT_BACKEND");
#endif
        if(!refused || actual.front()!=-12345.f) {std::cerr<<"Ascend request silently fell back\n";return 3;}
    }
    std::cout<<"{\"check\":\"strata_q2_expert_host_adapter\",\"outputs_compared\":"<<4*cpu::H<<",\"max_abs_error\":"<<largest<<",\"missing_native_backend_refused\":true,\"native_device_validated\":false,\"full_inference_validated\":false}\n";
}
