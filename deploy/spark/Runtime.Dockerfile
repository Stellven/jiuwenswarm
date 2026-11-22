ARG BASE_RUNTIME=ghcr.io/ggml-org/llama.cpp@sha256:695214dcb4d4062014335702caee98836bbf92c5974b78331c70e152176cbf08
FROM ${BASE_RUNTIME}
USER root
COPY app/ /opt/strata/
ENV LD_LIBRARY_PATH=/opt/strata:/usr/local/nvidia/lib:/usr/local/nvidia/lib64
WORKDIR /opt/strata
ENTRYPOINT ["/opt/strata/strata-dsv41"]
