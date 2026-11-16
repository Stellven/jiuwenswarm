#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iostream>
#include <vector>
#include <iomanip>
#include <stdexcept>
#include <string>
#include <algorithm>
#define CU(x) do {auto e=(x);if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}while(0)
#define BL(x) do {if((x)!=CUBLAS_STATUS_SUCCESS)throw std::runtime_error("cublas failure");}while(0)
__global__ void empty_kernel() {}
int main(int argc,char**argv){try{
 if(argc<6||argc>8)throw std::runtime_error("weights offset rows columns repeats [samples] [batch|each] required");
 auto offset=std::stoull(argv[2]);int m=std::stoi(argv[3]),n=std::stoi(argv[4]),reps=std::stoi(argv[5]);
 if(m<1||n<1||int64_t(m)*n>16777216||reps<1||reps>1000)throw std::runtime_error("bounded actual FP32 slice required");
 int samples=argc>=7?std::stoi(argv[6]):9;
 bool sync_each=argc==8&&std::string(argv[7])=="each";
 if(samples<1||samples>31||(argc==8&&std::string(argv[7])!="each"&&std::string(argv[7])!="batch"))throw std::runtime_error("samples 1..31 and batch|each required");
 std::vector<float>w(size_t(m)*n),x(n),y(m);std::vector<double>ref(m);
 auto start=std::chrono::steady_clock::now();std::ifstream file(argv[1],std::ios::binary);file.seekg(offset);file.read(reinterpret_cast<char*>(w.data()),w.size()*4);
 if(!file||size_t(file.gcount())!=w.size()*4)throw std::runtime_error("truncated weight slice");
 double read_s=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
 for(int k=0;k<n;k++)x[k]=float((k%17)-8)/17;
 for(int row=0;row<m;row++)for(int k=0;k<n;k++){float v=w[size_t(row)*n+k];if(!std::isfinite(v))throw std::runtime_error("nonfinite weight");ref[row]+=double(v)*x[k];}
 float *dw,*dx,*dy,*copy;CU(cudaMalloc(&dw,w.size()*4));CU(cudaMalloc(&copy,w.size()*4));CU(cudaMalloc(&dx,n*4));CU(cudaMalloc(&dy,m*4));
 CU(cudaMemcpy(dw,w.data(),w.size()*4,cudaMemcpyHostToDevice));CU(cudaMemcpy(dx,x.data(),n*4,cudaMemcpyHostToDevice));
 cublasHandle_t handle;BL(cublasCreate(&handle));BL(cublasSetMathMode(handle,CUBLAS_PEDANTIC_MATH));float alpha=1,beta=0;
 auto op=[&](){BL(cublasSgemv(handle,CUBLAS_OP_T,n,m,&alpha,dw,n,dx,1,&beta,dy,1));};
 for(int i=0;i<5;i++)op();CU(cudaDeviceSynchronize());cudaEvent_t a,b;CU(cudaEventCreate(&a));CU(cudaEventCreate(&b));
 auto timing=[&](auto operation){CU(cudaEventRecord(a));for(int i=0;i<reps;i++)operation();CU(cudaEventRecord(b));CU(cudaEventSynchronize(b));float ms;CU(cudaEventElapsedTime(&ms,a,b));return double(ms)/1000/reps;};
 double resident=timing(op);CU(cudaMemcpy(y.data(),dy,m*4,cudaMemcpyDeviceToHost));double error=0;bool correct=true;
 for(int i=0;i<m;i++){double e=std::abs(double(y[i])-ref[i]);error=std::max(error,e);correct &= std::isfinite(y[i])&&e<=1e-5+1e-5*std::abs(ref[i]);}
 // Paired boundaries on the same work. Event elapsed time is a stream interval,
 // not a pure kernel duration; host time includes event recording and completion.
 // Copy/check outputs outside each timed region, preserving any failed sample.
 struct Sample { double gpu_s,host_s,error;bool passed; };
 std::vector<Sample> paired;
 for(int sample=0;sample<samples;sample++){
   CU(cudaDeviceSynchronize());
   auto host_start=std::chrono::steady_clock::now();
   CU(cudaEventRecord(a));
   for(int i=0;i<reps;i++){op();if(sync_each)CU(cudaDeviceSynchronize());}
   CU(cudaEventRecord(b));CU(cudaEventSynchronize(b));
   double host_s=std::chrono::duration<double>(std::chrono::steady_clock::now()-host_start).count()/reps;
   float ms;CU(cudaEventElapsedTime(&ms,a,b));
   CU(cudaMemcpy(y.data(),dy,m*4,cudaMemcpyDeviceToHost));
   double sample_error=0;bool passed=true;
   for(int row=0;row<m;row++){
     double e=std::abs(double(y[row])-ref[row]);
     sample_error=std::max(sample_error,e);
     passed &= std::isfinite(y[row])&&e<=1e-5+1e-5*std::abs(ref[row]);
   }
   error=std::max(error,sample_error);correct &= passed;
   paired.push_back({double(ms)/1000/reps,host_s,sample_error,passed});
 }
 double copy_s=timing([&](){CU(cudaMemcpyAsync(copy,dw,w.size()*4,cudaMemcpyDeviceToDevice));});
 double launch_s=timing([&](){empty_kernel<<<1,1>>>();});CU(cudaGetLastError());
 std::cout<<std::setprecision(12)<<"{\"timing_schema\":1,\"synchronization\":\""<<(sync_each?"each":"batch")<<"\",\"warmup_operations\":5,\"paired_samples\":[";
 for(size_t i=0;i<paired.size();i++){const auto &v=paired[i];if(i)std::cout<<",";
   std::cout<<"{\"sample\":"<<i<<",\"gpu_event_s\":"<<v.gpu_s<<",\"synchronized_host_s\":"<<v.host_s<<",\"maximum_absolute_error\":"<<v.error<<",\"reference_passed\":"<<(v.passed?"true":"false")<<"}";
 }
 std::cout<<"],";
 std::cout<<std::setprecision(12)<<"\"kind\":\"measured_resident_slice\",\"numerical_path\":\"fp32_cublas_sgemv_pedantic\",\"rows\":"<<m<<",\"columns\":"<<n<<",\"repeats\":"<<reps<<",\"storage_read_s\":"<<read_s<<",\"storage_cache_state\":\"unknown\",\"resident_matvec_s\":"<<resident<<",\"copy_bandwidth_bytes_s\":"<<2*w.size()*4/copy_s<<",\"launch_overhead_s\":"<<launch_s<<",\"maximum_absolute_error\":"<<error<<",\"reference_passed\":"<<(correct?"true":"false")<<",\"activation_scope\":\"deterministic calibration input ((column%17)-8)/17, not captured activation\",\"whole_model_tokens_per_second\":null,\"observer_overhead\":\"unknown\"}\n";
 cublasDestroy(handle);cudaEventDestroy(a);cudaEventDestroy(b);cudaFree(dw);cudaFree(dx);cudaFree(dy);cudaFree(copy);return correct?0:2;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
