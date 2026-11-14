#include "strata_core.h"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
struct OperationCheck {
 std::string source_id,name,operation,status="unverified",error;
 long long outputs_compared=0;double max_abs_error=0;
};
static void compare(OperationCheck& check,float actual,float expected){
 check.outputs_compared++;
 if(!std::isfinite(actual)||!std::isfinite(expected))throw std::runtime_error("non-finite numerical comparison");
 const double error=std::abs(double(actual)-double(expected));
 check.max_abs_error=std::max(check.max_abs_error,error);
 if(error>1e-5)throw std::runtime_error("independent numerical reference mismatch");
}
static void quote(const std::string& value){
 std::cout<<'"';for(unsigned char c:value){
  if(c=='"'||c=='\\')std::cout<<'\\'<<c;
  else if(c=='\n')std::cout<<"\\n";else if(c=='\r')std::cout<<"\\r";else if(c=='\t')std::cout<<"\\t";
  else if(c<32)std::cout<<"\\u00"<<"0123456789abcdef"[c>>4]<<"0123456789abcdef"[c&15];
  else std::cout<<c;
 }std::cout<<'"';
}
namespace upstream {constexpr double RENORM_CLAMP=6.103515625e-05;
void reference(const float* logits, int n_expert, int k, int* ids, float* w) {
    double mx = logits[0];
    for (int e = 1; e < n_expert; ++e) mx = std::max(mx, (double) logits[e]);
    double sum = 0;
    std::vector<double> p((size_t) n_expert);
    for (int e = 0; e < n_expert; ++e) {
        p[(size_t) e] = std::exp((double) logits[e] - mx);
        sum += p[(size_t) e];
    }
    for (int e = 0; e < n_expert; ++e) p[(size_t) e] /= sum;

    // stable descending: std::stable_sort with a strict greater-than keeps equal elements in index order
    std::vector<int> idx((size_t) n_expert);
    std::iota(idx.begin(), idx.end(), 0);
    std::stable_sort(idx.begin(), idx.end(),
                     [&](int a, int b) { return p[(size_t) a] > p[(size_t) b]; });
    double s = 0;
    for (int i = 0; i < k; ++i) {
        ids[i] = idx[(size_t) i];
        w[i] = (float) p[(size_t) idx[(size_t) i]];
        s += p[(size_t) idx[(size_t) i]];
    }
    s = std::max(s, RENORM_CLAMP);
    for (int i = 0; i < k; ++i) w[i] = (float) ((double) w[i] / s);
}
}
int main(){std::vector<OperationCheck> checks;bool failed=false;
checks.push_back({"src/kernels/cuda/router_top10.cu:router_top10_kernel","router_top10_kernel","router"});
{auto& check=checks.back();try{
std::mt19937 rng(20261114);std::normal_distribution<float> normal;
for(int trial=0;trial<20;++trial){
 int n=trial%2?512:37,k=trial%3?10:1;
 std::vector<float> values(n),weights(k);std::vector<int> ids(k);for(auto& v:values)v=normal(rng);
 auto actual=strata_core::invoke_49ab87035bb021f7(values,k);upstream::reference(values.data(),n,k,ids.data(),weights.data());
 for(int i=0;i<k;++i){
  check.outputs_compared++;if(actual.ids[i]!=ids[i])throw std::runtime_error("upstream host router expert selection mismatch");
  compare(check,actual.weights[i],weights[i]);
 }
}
std::vector<float> tied(512,0.f);tied[511]=1e-10f;auto tied_result=strata_core::invoke_49ab87035bb021f7(tied,10);
for(int i=0;i<10;++i){check.outputs_compared++;if(tied_result.ids[i]!=i)throw std::runtime_error("production rounded tie order mismatch");}
if(check.outputs_compared>0)check.status="passed";
}catch(const std::exception& error){check.status="failed";check.error=error.what();failed=true;}}
checks.push_back({"src/kernels/cuda/elementwise.cu:scale_kernel","scale_kernel","elementwise"});
{auto& check=checks.back();try{
check.status="unverified";check.error="No built-in independent semantic oracle for this selected source; external oracle required";
}catch(const std::exception& error){check.status="failed";check.error=error.what();failed=true;}}
long long compared=0;double maximum=0;bool complete=true;
for(const auto& check:checks){compared+=check.outputs_compared;maximum=std::max(maximum,check.max_abs_error);complete=complete&&check.status=="passed";}
std::cout<<std::setprecision(17)<<"{\"check\":\"source_lowered_strata_core\",\"outputs_compared\":"<<compared<<",\"max_abs_error\":"<<maximum<<",\"coverage_complete\":"<<(complete?"true":"false")<<",\"operation_checks\":[";
for(size_t i=0;i<checks.size();++i){const auto& check=checks[i];if(i)std::cout<<',';
 std::cout<<"{\"source_id\":";quote(check.source_id);std::cout<<",\"name\":";quote(check.name);
 std::cout<<",\"operation\":";quote(check.operation);std::cout<<",\"status\":";quote(check.status);
 std::cout<<",\"outputs_compared\":"<<check.outputs_compared<<",\"max_abs_error\":"<<check.max_abs_error;
 if(!check.error.empty()){std::cout<<",\"error\":";quote(check.error);}std::cout<<'}';
}
std::cout<<"],\"native_device_validated\":false,\"full_inference_validated\":false}\n";
return failed?1:0;}
