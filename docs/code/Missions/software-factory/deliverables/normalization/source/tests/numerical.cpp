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
int main(){std::vector<OperationCheck> checks;bool failed=false;
checks.push_back({"src/kernels/cuda/elementwise.cu:rms_norm_weighted_kernel","rms_norm_weighted_kernel","rms_norm"});
{auto& check=checks.back();try{
std::mt19937 rng(20261114);std::normal_distribution<float> normal;
const int rows=3,cols=33;const float eps=1e-5f;
std::vector<float> original(rows*cols),actual,weights(cols);for(auto& v:original)v=normal(rng);for(auto& v:weights)v=normal(rng);
actual=original;strata_core::invoke_c9b0d6f190bcc119(actual.data(),weights.data(),rows,cols,eps);
for(int row=0;row<rows;++row){
 float partial[32]={};for(int lane=0;lane<32;++lane)for(int c=lane;c<cols;c+=32)partial[lane]+=original[row*cols+c]*original[row*cols+c];
 for(int offset=16;offset>0;offset>>=1){float previous[32];std::copy(partial,partial+32,previous);for(int lane=0;lane<32;++lane)partial[lane]+=previous[lane+offset<32?lane+offset:lane];}
 const float inv=1.f/std::sqrt(partial[0]/float(cols)+eps);
 for(int c=0;c<cols;++c){const float expected=(original[row*cols+c]*weights[c])*inv;compare(check,actual[row*cols+c],expected);}
}
if(check.outputs_compared>0)check.status="passed";
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
