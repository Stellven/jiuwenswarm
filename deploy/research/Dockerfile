# Runtime packaging is separate from restricted scientific POC execution.
# Prepare images/runtime wheels explicitly before use; startup downloads nothing.
FROM python:3.13-slim
WORKDIR /opt/ai4research
RUN groupadd --gid 10001 research && useradd --uid 10001 --gid research --create-home research
COPY jiuwenswarm/__init__.py ./jiuwenswarm/__init__.py
COPY jiuwenswarm/research ./jiuwenswarm/research
COPY jiuwenswarm/server/__init__.py ./jiuwenswarm/server/__init__.py
COPY jiuwenswarm/server/runtime/__init__.py ./jiuwenswarm/server/runtime/__init__.py
COPY jiuwenswarm/server/runtime/codex_subscription/transport.py ./jiuwenswarm/server/runtime/codex_subscription/transport.py
COPY jiuwenswarm/server/runtime/codex_subscription/__init__.py ./jiuwenswarm/server/runtime/codex_subscription/__init__.py
# Optional prebuilt React assets can be supplied by a derived prepared image.
# The shipped HTML entry needs no npm or runtime dependencies.
RUN mkdir -p /var/lib/ai4research/state /var/lib/ai4research/account /campaign && chown -R research:research /var/lib/ai4research /campaign
USER research
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AI4R_ACCOUNT_HOME=/var/lib/ai4research/account
EXPOSE 5173
ENTRYPOINT ["python", "-m", "jiuwenswarm.research"]
CMD ["serve", "--host", "0.0.0.0", "--port", "5173", "--state-dir", "/var/lib/ai4research/state", "--container-private-network"]
