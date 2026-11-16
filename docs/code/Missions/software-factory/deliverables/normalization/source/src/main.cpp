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
 std::string path,operation="rms_norm";
 for(int i=1;i<argc;++i){std::string key=argv[i];if((key=="--input"||key=="--operation")&&i+1<argc){if(key=="--input")path=argv[++i];else operation=argv[++i];}else throw std::runtime_error("usage: strata_engine --input PATH [--operation FUNCTION]");}
 if(path.empty())throw std::runtime_error("--input is required");std::ifstream input(path);if(!input)throw std::runtime_error("cannot open input");std::cout<<std::setprecision(9);
if(operation=="rms_norm_weighted_kernel"||operation=="src/kernels/cuda/elementwise.cu:rms_norm_weighted_kernel"||operation=="rms_norm"||operation=="normalization"){int64_t rows,cols;float eps;if(!(input>>rows>>cols>>eps)||rows<1||rows>100000||cols<1||cols>65536||rows*cols>16777216)throw std::runtime_error("invalid normalization shape");std::vector<float> values(size_t(rows*cols)),weights(cols);read(input,values);read(input,weights);strata_core::invoke_c9b0d6f190bcc119(values.data(),weights.data(),rows,cols,eps);emit(values);}else throw std::runtime_error("requested operation is not in this compiled capability set");
 std::string extra;if(input>>extra)throw std::runtime_error("unexpected trailing input");std::cout<<"\n";return 0;
 }catch(const std::exception& error){std::cerr<<error.what()<<"\n";return 2;}}
