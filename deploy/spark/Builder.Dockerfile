ARG BUILDER_BASE=ghcr.io/ggml-org/llama.cpp@sha256:695214dcb4d4062014335702caee98836bbf92c5974b78331c70e152176cbf08
FROM ${BUILDER_BASE}
COPY system/ /
COPY cmake/ /opt/toolchain/cmake/
COPY bin/ /opt/toolchain/bin/
COPY toolchain.json /opt/toolchain/toolchain.json
RUN ln -sfn gcc-13 /usr/bin/gcc && ln -sfn g++-13 /usr/bin/g++ && \
    ln -sfn gcc-13 /usr/bin/cc && ln -sfn g++-13 /usr/bin/c++ && \
    ln -sfn aarch64-linux-gnu-as /usr/bin/as && ln -sfn aarch64-linux-gnu-ld /usr/bin/ld && \
    ln -sfn aarch64-linux-gnu-ar /usr/bin/ar && ln -sfn aarch64-linux-gnu-ranlib /usr/bin/ranlib && \
    ln -sfn /usr/local/cuda-13.0 /usr/local/cuda
ENV PATH=/opt/toolchain/cmake/bin:/opt/toolchain/bin:/usr/local/cuda/bin:/usr/bin:/bin \
    CC=/usr/bin/gcc-13 CXX=/usr/bin/g++-13 CUDAHOSTCXX=/usr/bin/g++-13 CUDACXX=/usr/local/cuda/bin/nvcc
RUN nvcc --version && gcc --version && cmake --version && ninja --version && \
    printf '#include <iostream>\nint main(){std::cout<<42;}\n' >/tmp/test.cpp && \
    g++ /tmp/test.cpp -o /tmp/compiler-check && test "$(/tmp/compiler-check)" = 42 && \
    rm /tmp/test.cpp /tmp/compiler-check
ENTRYPOINT ["/usr/bin/python3"]
