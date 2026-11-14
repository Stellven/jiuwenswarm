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
 std::string path,operation="operations";
 for(int i=1;i<argc;++i){std::string key=argv[i];if((key=="--input"||key=="--operation")&&i+1<argc){if(key=="--input")path=argv[++i];else operation=argv[++i];}else throw std::runtime_error("usage: strata_engine --input PATH [--operation FUNCTION]");}
 if(path.empty())throw std::runtime_error("--input is required");std::ifstream input(path);if(!input)throw std::runtime_error("cannot open input");std::cout<<std::setprecision(9);
if(operation=="router_top10_kernel"||operation=="src/kernels/cuda/router_top10.cu:router_top10_kernel"||operation=="router"||operation=="routing"){int n,k;if(!(input>>n>>k)||n<1||n>512||k<1||k>n)throw std::runtime_error("invalid N/K shape");std::vector<float> x(n);read(input,x);auto value=strata_core::invoke_49ab87035bb021f7(x,k);emit(value);}else if(operation=="scale_kernel"||operation=="src/kernels/cuda/elementwise.cu:scale_kernel"||operation=="elementwise"||operation=="elementwise"){int n;if(!(input>>n)||n<1||n>16777216)throw std::runtime_error("invalid elementwise N");
float scalar_0;if(!(input>>scalar_0)||!std::isfinite(scalar_0))throw std::runtime_error("invalid scalar input");
std::vector<float> tensor_0(n);
read(input,tensor_0);
strata_core::invoke_99a12ae78535eaee(tensor_0.data(),n,scalar_0);
emit(tensor_0);}else throw std::runtime_error("requested operation is not in this compiled capability set");
 std::string extra;if(input>>extra)throw std::runtime_error("unexpected trailing input");std::cout<<"\n";return 0;
 }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 2;}}
