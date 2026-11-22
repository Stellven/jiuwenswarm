ARG BASE_RUNTIME=nvcr.io/nvidia/l4t-cuda:12.6.11-runtime@sha256:49853e9fe2a0305efa51fcbb3426eea1bca658085f2d26bb40347711434849b1
FROM ${BASE_RUNTIME}
ARG SOURCE_COMMIT
ARG SOURCE_TREE
ARG PATCH_SHA256
ARG TOOLCHAIN
ARG TARGET_PROFILE=jetson-orin
LABEL org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      campaign.source.tree="${SOURCE_TREE}" \
      campaign.patch.sha256="${PATCH_SHA256}" \
      campaign.toolchain="${TOOLCHAIN}" \
      campaign.target.profile="${TARGET_PROFILE}"
COPY app/ /app/
ENV LD_LIBRARY_PATH=/app
ENV NVIDIA_VISIBLE_DEVICES=all NVIDIA_DRIVER_CAPABILITIES=compute,utility
WORKDIR /app
ENTRYPOINT []
CMD ["/app/llama-cli", "--help"]
