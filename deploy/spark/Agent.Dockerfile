# Existing Ubuntu 24.04 / ARM64 CUDA runtime matches the imported native wheels.
ARG AGENT_BASE=ghcr.io/ggml-org/llama.cpp@sha256:695214dcb4d4062014335702caee98836bbf92c5974b78331c70e152176cbf08
FROM ${AGENT_BASE}
COPY system/ /
COPY site/ /opt/factory-site/
COPY jiuwenswarm/ /factory/jiuwenswarm/
COPY deploy/spark/ /factory/deploy/spark/
COPY closure.json requirements-agent.lock /opt/factory-provenance/
ENV PYTHONPATH=/factory:/opt/factory-site JIUWENSWARM_SKIP_DOTENV=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /tmp
RUN /usr/bin/python3 -c "from jiuwenswarm.server.runtime.agent_adapter.interface import JiuWenSwarm; from importlib.metadata import version; assert version('openai-codex-cli-bin') == '0.163.0'; print('factory-agent-import-ok')"
ENTRYPOINT ["/usr/bin/python3", "-m", "jiuwenswarm.factory.cli"]
