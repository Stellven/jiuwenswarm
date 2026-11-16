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
#include <cctype>
#include <cstdint>
#define CU(x) do {auto e=(x);if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}while(0)
#define BL(x) do {if((x)!=CUBLAS_STATUS_SUCCESS)throw std::runtime_error("cublas failure");}while(0)
__global__ void empty_kernel() {}
int main(int argc,char**argv){try{
 if(argc<6||argc>10||argc==9)throw std::runtime_error("weights offset rows columns repeats [samples] [batch|each] [run_id tensor_id] required");
 auto offset=std::stoull(argv[2]);int m=std::stoi(argv[3]),n=std::stoi(argv[4]),reps=std::stoi(argv[5]);
 if(m<1||n<1||int64_t(m)*n>16777216||reps<1||reps>1000)throw std::runtime_error("bounded actual FP32 slice required");
 int samples=argc>=7?std::stoi(argv[6]):9;
 bool sync_each=argc>=8&&std::string(argv[7])=="each";
 if(samples<1||samples>31||(argc>=8&&std::string(argv[7])!="each"&&std::string(argv[7])!="batch"))throw std::runtime_error("samples 1..31 and batch|each required");
 bool replay=argc==10;
 if(replay){
   if(m>4096||n>262144)throw std::runtime_error("replay vector bound exceeded");
   for(int i=8;i<10;i++){
     std::string id(argv[i]);if(id.empty()||id.size()>128)throw std::runtime_error("bounded replay identity required");
     for(unsigned char c:id)if(!std::isalnum(c)&&c!='_'&&c!='-'&&c!='.')throw std::runtime_error("invalid replay identity");
   }
 }
 std::vector<float> outputs;
 if(replay)outputs.reserve(size_t(m)*(samples+1));
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
 if(replay)outputs.insert(outputs.end(),y.begin(),y.end());
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
   if(replay)outputs.insert(outputs.end(),y.begin(),y.end());
   paired.push_back({double(ms)/1000/reps,host_s,sample_error,passed});
 }
 double copy_s=timing([&](){CU(cudaMemcpyAsync(copy,dw,w.size()*4,cudaMemcpyDeviceToDevice));});
 double launch_s=timing([&](){empty_kernel<<<1,1>>>();});CU(cudaGetLastError());
 // File serialization occurs after all measured regions. Existing /out collection owns
 // transport, digests and cleanup; these files never certify themselves.
 if(replay){
   auto write=[](const char* path,const void* data,size_t size){
     std::ofstream f(path,std::ios::binary);f.write(static_cast<const char*>(data),size);f.close();
     if(!f)throw std::runtime_error("replay artifact write failed");
   };
   uint32_t endian=1;if(*reinterpret_cast<unsigned char*>(&endian)!=1)throw std::runtime_error("little endian replay required");
   write("/out/input.f32",x.data(),x.size()*4);
   write("/out/reference.f64",ref.data(),ref.size()*8);
   write("/out/output.f32",outputs.data(),outputs.size()*4);
   std::ofstream meta("/out/replay.json");
   meta<<"{\"format\":\"factory-fp32-replay/1\",\"criterion\":\"abs(error)<=1e-5+1e-5*abs(reference)\",\"run_id\":\""<<argv[8]<<"\",\"tensor_id\":\""<<argv[9]<<"\",\"offset\":"<<offset<<",\"shape\":["<<m<<","<<n<<"],\"repeats\":"<<reps<<",\"samples\":"<<samples<<",\"synchronization\":\""<<(sync_each?"each":"batch")<<"\",\"input_kind\":\"calibration_mod17\"}\n";
   meta.close();if(!meta)throw std::runtime_error("replay metadata write failed");
 }
 std::cout<<std::setprecision(12)<<"{\"timing_schema\":1,\"synchronization\":\""<<(sync_each?"each":"batch")<<"\",\"warmup_operations\":5,\"paired_samples\":[";
 for(size_t i=0;i<paired.size();i++){const auto &v=paired[i];if(i)std::cout<<",";
   std::cout<<"{\"sample\":"<<i<<",\"gpu_event_s\":"<<v.gpu_s<<",\"synchronized_host_s\":"<<v.host_s<<",\"maximum_absolute_error\":"<<v.error<<",\"reference_passed\":"<<(v.passed?"true":"false")<<"}";
 }
 std::cout<<"],\"independent_numerical_verification\":\"unverified\",\"replay_material_retained\":"<<(replay?"true":"false")<<",";
 std::cout<<std::setprecision(12)<<"\"kind\":\"measured_resident_slice\",\"numerical_path\":\"fp32_cublas_sgemv_pedantic\",\"rows\":"<<m<<",\"columns\":"<<n<<",\"repeats\":"<<reps<<",\"storage_read_s\":"<<read_s<<",\"storage_cache_state\":\"unknown\",\"resident_matvec_s\":"<<resident<<",\"copy_bandwidth_bytes_s\":"<<2*w.size()*4/copy_s<<",\"launch_overhead_s\":"<<launch_s<<",\"maximum_absolute_error\":"<<error<<",\"reference_passed\":"<<(correct?"true":"false")<<",\"activation_scope\":\"deterministic calibration input ((column%17)-8)/17, not captured activation\",\"whole_model_tokens_per_second\":null,\"observer_overhead\":\"unknown\"}\n";
 cublasDestroy(handle);cudaEventDestroy(a);cudaEventDestroy(b);cudaFree(dw);cudaFree(dx);cudaFree(dy);cudaFree(copy);return correct?0:2;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
