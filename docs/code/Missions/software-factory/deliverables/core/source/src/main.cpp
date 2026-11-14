#include "strata_core.h"
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static void read(std::istream& input,std::vector<float>& values){for(auto& v:values)if(!(input>>v)||!std::isfinite(v))throw std::runtime_error("missing/non-finite input value");}
static void array(const std::vector<float>& values){for(size_t i=0;i<values.size();++i){if(!std::isfinite(values[i]))throw std::runtime_error("non-finite computed output");std::cout<<(i?",":"")<<values[i];}}
static void emit(const std::vector<float>& values){std::cout<<"{\"backend\":\""<<strata_core::backend()<<"\",\"output\":[";array(values);std::cout<<"]}";}
static void emit(const strata_core::Routing& routing){std::cout<<"{\"backend\":\""<<strata_core::backend()<<"\",\"ids\":[";for(size_t i=0;i<routing.ids.size();++i)std::cout<<(i?",":"")<<routing.ids[i];std::cout<<"],\"weights\":[";array(routing.weights);std::cout<<"]}";}
int main(int argc,char** argv){try{
 std::string path,operation="combined";
 for(int i=1;i<argc;++i){std::string key=argv[i];if((key=="--input"||key=="--operation")&&i+1<argc){if(key=="--input")path=argv[++i];else operation=argv[++i];}else throw std::runtime_error("usage: strata_engine --input PATH [--operation FUNCTION]");}
 if(path.empty())throw std::runtime_error("--input is required");std::ifstream input(path);if(!input)throw std::runtime_error("cannot open input");std::cout<<std::setprecision(9);
if(operation=="combined"){
 int n,k,d;if(!(input>>n>>k>>d)||n<1||n>512||k<1||k>n||d<1||d>65536)throw std::runtime_error("invalid combined tensor shapes");
 std::vector<float> logits(n),gate(size_t(n)*d),up(gate.size()),activated(gate.size()),shared(d),parts(size_t(k)*d),output(d);
 read(input,logits);read(input,gate);read(input,up);read(input,shared);auto routing=strata_core::route(logits,k);
 strata_core::swiglu(gate.data(),up.data(),activated.data(),int(activated.size()));
 for(int e=0;e<k;++e)for(int j=0;j<d;++j)parts[size_t(e)*d+j]=activated[size_t(routing.ids[e])*d+j];
 strata_core::moe_combine(parts.data(),routing.weights.data(),shared.data(),output.data(),d,k,1);
 std::cout<<"{\"backend\":\""<<strata_core::backend()<<"\",\"ids\":[";for(int i=0;i<k;++i)std::cout<<(i?",":"")<<routing.ids[i];
 std::cout<<"],\"weights\":[";array(routing.weights);std::cout<<"],\"output\":[";array(output);std::cout<<"]}";
 }else if(operation=="router_top10_kernel"||operation=="src/kernels/cuda/router_top10.cu:router_top10_kernel"||operation=="router"||operation=="routing"){int n,k;if(!(input>>n>>k)||n<1||n>512||k<1||k>n)throw std::runtime_error("invalid N/K shape");std::vector<float> x(n);read(input,x);auto value=strata_core::invoke_49ab87035bb021f7(x,k);emit(value);}else if(operation=="swiglu_kernel"||operation=="src/kernels/cuda/shared_expert.cu:swiglu_kernel"||operation=="swiglu"||operation=="activation"){int n;if(!(input>>n)||n<1||n>16777216)throw std::runtime_error("invalid N");std::vector<float> gate(n),up(n),output(n);read(input,gate);read(input,up);strata_core::invoke_82afe71f227b1515(gate.data(),up.data(),output.data(),n);emit(output);}else if(operation=="moe_combine_kernel"||operation=="src/kernels/cuda/shared_expert.cu:moe_combine_kernel"||operation=="moe_combine"||operation=="aggregation"){int k,d;if(!(input>>k>>d)||k<1||k>512||d<1||d>65536)throw std::runtime_error("invalid K/D");std::vector<float> weights(k),parts(size_t(k)*d),shared(d),output(d);read(input,weights);read(input,parts);read(input,shared);strata_core::invoke_6f47e6c5df6f167e(parts.data(),weights.data(),shared.data(),output.data(),d,k,1);emit(output);}else throw std::runtime_error("requested operation is not in this compiled capability set");
 std::string extra;if(input>>extra)throw std::runtime_error("unexpected trailing input");std::cout<<"\n";return 0;
 }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 2;}}
