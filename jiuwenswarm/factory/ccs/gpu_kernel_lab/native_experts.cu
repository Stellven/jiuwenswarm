#include <cuda_runtime.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <vector>
#define C(x) do{auto e=(x);if(e!=cudaSuccess){std::cerr<<cudaGetErrorString(e)<<" at "<<__LINE__<<"\n";exit(3);}}while(0)
// Each CTA computes one routed token/output row. Weight fetches coalesce over K.
// Baseline launches the identical CTA kernel separately for each route.
__global__ void row_gemv(const float*w,const float*x,const int*ids,float*part,int M,int K,int R,int route0,int count){
 int row=blockIdx.x, route=route0+blockIdx.y;if(blockIdx.y>=count)return;
 int token=route/R,expert=ids[route];float sum=0;
 for(int k=threadIdx.x;k<K;k+=blockDim.x)sum+=w[(expert*M+row)*K+k]*x[token*K+k];
 extern __shared__ float s[];s[threadIdx.x]=sum;__syncthreads();
 for(int stride=blockDim.x/2;stride;stride/=2){if(threadIdx.x<stride)s[threadIdx.x]+=s[threadIdx.x+stride];__syncthreads();}
 if(threadIdx.x==0)part[route*M+row]=s[0];
}
__global__ void combine(const float*p,const float*g,float*y,int M,int T,int R){int z=blockIdx.x*blockDim.x+threadIdx.x;if(z<T*M){int t=z/M,m=z%M;float v=0;for(int r=0;r<R;r++)v+=p[(t*R+r)*M+m]*g[t*R+r];y[z]=v;}}
int main(){int E,M,K,T,R,reps;if(!(std::cin>>E>>M>>K>>T>>R>>reps)||E<1||E>32||M<1||M>2048||K<1||K>2048||T<1||T>64||R<1||R>8||R>E||reps<5||reps>1000||int64_t(E)*M*K>262144||int64_t(T)*R*M*K>16777216)return 2;
 std::vector<float>w(E*M*K),x(T*K),g(T*R);std::vector<int>ids(T*R);for(auto*a:{&w,&x,&g})for(float&v:*a){if(!(std::cin>>v)||!std::isfinite(v)||std::abs(v)>1e6)return 2;}for(int&v:ids)if(!(std::cin>>v)||v<0||v>=E)return 2;
 std::vector<double>ref(T*M,0);for(int t=0;t<T;t++)for(int m=0;m<M;m++)for(int r=0;r<R;r++){double dot=0;for(int k=0;k<K;k++)dot+=double(w[(ids[t*R+r]*M+m)*K+k])*double(x[t*K+k]);ref[t*M+m]+=dot*double(g[t*R+r]);}
 float *dw,*dx,*dg,*dp,*dy;int*di;C(cudaMalloc(&dw,w.size()*4));C(cudaMalloc(&dx,x.size()*4));C(cudaMalloc(&dg,g.size()*4));C(cudaMalloc(&di,ids.size()*4));C(cudaMalloc(&dp,T*R*M*4));C(cudaMalloc(&dy,T*M*4));
 C(cudaMemcpy(dw,w.data(),w.size()*4,cudaMemcpyHostToDevice));C(cudaMemcpy(dx,x.data(),x.size()*4,cudaMemcpyHostToDevice));C(cudaMemcpy(dg,g.data(),g.size()*4,cudaMemcpyHostToDevice));C(cudaMemcpy(di,ids.data(),ids.size()*4,cudaMemcpyHostToDevice));
 cudaDeviceProp prop;int dev;C(cudaGetDevice(&dev));C(cudaGetDeviceProperties(&prop,dev));cudaEvent_t a,b;C(cudaEventCreate(&a));C(cudaEventCreate(&b));
 std::vector<float>out(T*M);bool correct=true;double worst=0;float best=1e30,baseline=0;int best_threads=0;std::vector<float>times;
 auto launch=[&](int threads,bool serial){if(serial){for(int route=0;route<T*R;route++)row_gemv<<<dim3(M,1),threads,threads*4>>>(dw,dx,di,dp,M,K,R,route,1);}else row_gemv<<<dim3(M,T*R),threads,threads*4>>>(dw,dx,di,dp,M,K,R,0,T*R);combine<<<(T*M+127)/128,128>>>(dp,dg,dy,M,T,R);};
 for(int variant=-1;variant<4;variant++){int threads=variant<0?128:(32<<variant);bool serial=variant<0;for(int i=0;i<5;i++)launch(threads,serial);C(cudaDeviceSynchronize());C(cudaEventRecord(a));for(int i=0;i<reps;i++)launch(threads,serial);C(cudaEventRecord(b));C(cudaEventSynchronize(b));float ms;C(cudaEventElapsedTime(&ms,a,b));ms/=reps;C(cudaGetLastError());C(cudaMemcpy(out.data(),dy,T*M*4,cudaMemcpyDeviceToHost));double err=0,scale=0;for(int z=0;z<T*M;z++){err=std::max(err,std::abs(double(out[z])-ref[z]));scale=std::max(scale,std::abs(ref[z]));}correct &= err<=2e-5+2e-5*scale;worst=std::max(worst,err);if(serial)baseline=ms;else{times.push_back(ms);if(ms<best){best=ms;best_threads=threads;}}}
 // Return the selected configuration, not whichever candidate happened to run last.
 launch(best_threads,false);C(cudaDeviceSynchronize());C(cudaMemcpy(out.data(),dy,T*M*4,cudaMemcpyDeviceToHost));
 std::cout<<std::setprecision(10)<<"{\"device\":\""<<prop.name<<"\",\"cuda_sm\":"<<prop.major*10+prop.minor<<",\"serial_route_ms\":"<<baseline<<",\"best_batched_ms\":"<<best<<",\"speedup\":"<<baseline/best<<",\"best_threads\":"<<best_threads<<",\"baseline_launches\":"<<T*R+1<<",\"batched_launches\":2,\"repeats\":"<<reps<<",\"all_variants_correct\":"<<(correct?"true":"false")<<",\"native_max_abs_error\":"<<worst<<",\"candidate_ms\":[";for(size_t i=0;i<times.size();i++){if(i)std::cout<<",";std::cout<<times[i];}std::cout<<"],\"output\":[";for(size_t i=0;i<out.size();i++){if(i)std::cout<<",";std::cout<<out[i];}std::cout<<"]}\n";
 C(cudaEventDestroy(a));C(cudaEventDestroy(b));for(float*p:{dw,dx,dg,dp,dy})C(cudaFree(p));C(cudaFree(di));}
