ARG BASE_DEVEL=nvidia/cuda:12.8.1-devel-ubuntu24.04
ARG BASE_DEVEL_DIGEST
ARG BASE_RUNTIME=nvidia/cuda:12.8.1-runtime-ubuntu24.04
ARG BASE_RUNTIME_DIGEST

FROM ${BASE_DEVEL}@${BASE_DEVEL_DIGEST} AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git libgomp1 ccache && rm -rf /var/lib/apt/lists/*
WORKDIR /src
ARG EXTRA_TARGETS=""
COPY . .
# ccache lives in a BuildKit cache mount: candidate rebuilds recompile only what a patch touches.
RUN --mount=type=cache,id=llamacpp-ccache,target=/root/.ccache \
    cmake -S . -B /build \
    -DCMAKE_BUILD_TYPE=Release \
    -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120 \
    -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=ON \
    -DGGML_NATIVE=OFF -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF -DLLAMA_OPENSSL=OFF \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache -DCMAKE_CUDA_COMPILER_LAUNCHER=ccache \
    -DCMAKE_EXE_LINKER_FLAGS=-Wl,--allow-shlib-undefined \
    && cmake --build /build --parallel 10 --target \
    llama-bench llama-perplexity llama-completion llama-server \
    llama-eval-callback llama-cli llama-tokenize ${EXTRA_TARGETS} && ccache -s
# Preserve SONAME symlinks. Include the OpenMP runtime from the builder.
RUN mkdir /runtime && \
    for tool in llama-bench llama-perplexity llama-completion llama-server \
        llama-eval-callback llama-cli llama-tokenize ${EXTRA_TARGETS}; do \
        cp /build/bin/"$tool" /runtime/; \
    done && \
    cp -a /build/bin/*.so* /runtime/ && \
    cp -L /usr/lib/x86_64-linux-gnu/libgomp.so.1 /runtime/

FROM ${BASE_RUNTIME}@${BASE_RUNTIME_DIGEST} AS runtime
ARG SOURCE_COMMIT
ARG PATCH_SHA256
LABEL org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      campaign.patch.sha256="${PATCH_SHA256}"
COPY --from=builder /runtime/ /app/
ENV LD_LIBRARY_PATH=/app:/usr/local/nvidia/lib:/usr/local/nvidia/lib64
WORKDIR /app
# Clear the CUDA base's inherited entrypoint as well.
ENTRYPOINT []
CMD ["/app/llama-cli", "--help"]
