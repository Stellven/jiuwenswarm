# syntax=docker/dockerfile:1.7
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
ARG NODE_IMAGE=node:22-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1
FROM ${UV_IMAGE} AS uv
FROM ${NODE_IMAGE} AS node
FROM ${PYTHON_IMAGE} AS runtime-tools
COPY --from=uv /uv /uvx /usr/local/bin/
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates bubblewrap tmux procps iproute2 util-linux \
    libgomp1 libglib2.0-0 libgl1 gcc g++ \
    && dpkg-query -W > /usr/local/share/ai4r-os-packages.txt \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 10001 ai4r && useradd --uid 10001 --gid 10001 --create-home ai4r \
    && groupadd --gid 10002 executor && useradd --uid 10002 --gid 10002 --no-create-home executor \
    && groupadd --gid 13100 routing_public \
    && groupadd --gid 10011 router && useradd --uid 10011 --gid 13100 --no-create-home router \
    && usermod --append --groups routing_public ai4r
ENV UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:/usr/local/bin:/usr/bin:/bin
WORKDIR /opt/ai4r

FROM runtime-tools AS dependencies
COPY pyproject.toml uv.lock LICENSE OPEN_SOURCE_SOFTWARE_NOTICE.md ./
COPY packages/jiuwenswarm-tui/ ./packages/jiuwenswarm-tui/
COPY jiuwenbox/ ./jiuwenbox/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-default-groups --extra codex --extra tui --no-install-project

FROM runtime-tools AS codex-qualification
COPY deploy/m1/requirements-cli.txt /tmp/requirements-cli.txt
RUN uv pip install --system --no-deps --require-hashes -r /tmp/requirements-cli.txt
COPY deploy/m1/qualify_codex.py /usr/local/bin/qualify_codex.py
ENTRYPOINT ["python", "/usr/local/bin/qualify_codex.py"]

FROM node AS frontend
WORKDIR /build/jiuwenswarm/channels/web/frontend
COPY jiuwenswarm/channels/web/frontend/package.json jiuwenswarm/channels/web/frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
WORKDIR /build
COPY scripts/ ./scripts/
COPY jiuwenswarm/scripts/ ./jiuwenswarm/scripts/
COPY jiuwenswarm/resources/agent/ ./jiuwenswarm/resources/agent/
COPY jiuwenswarm/research_contracts/ ./jiuwenswarm/research_contracts/
COPY jiuwenswarm/channels/web/frontend/ ./jiuwenswarm/channels/web/frontend/
WORKDIR /build/jiuwenswarm/channels/web/frontend
RUN npm run build

FROM node AS tui
WORKDIR /build/jiuwenswarm/channels/tui/frontend
COPY jiuwenswarm/channels/tui/frontend/package.json jiuwenswarm/channels/tui/frontend/package-lock.json ./
RUN npm ci
COPY jiuwenswarm/channels/tui/frontend/src/ ./src/
COPY jiuwenswarm/channels/tui/frontend/tsconfig.json ./
RUN npm run build && npm prune --omit=dev --offline

FROM dependencies AS application-build
COPY jiuwenswarm/ ./jiuwenswarm/
COPY --from=frontend /build/jiuwenswarm/channels/web/frontend/dist ./jiuwenswarm/channels/web/frontend/dist
COPY --from=tui /build/jiuwenswarm/channels/tui/frontend/dist/ ./jiuwenswarm/channels/tui/frontend/dist/
COPY --from=tui /build/jiuwenswarm/channels/tui/frontend/node_modules/ ./jiuwenswarm/channels/tui/frontend/node_modules/
COPY --from=tui /build/jiuwenswarm/channels/tui/frontend/package.json ./jiuwenswarm/channels/tui/frontend/package.json
RUN uv build --wheel --python /opt/venv/bin/python --offline --no-cache --no-build-isolation --no-build-logs --out-dir /opt/ai4r-wheels packages/jiuwenswarm-tui \
    && uv pip install --python /opt/venv/bin/python --offline --no-deps --reinstall /opt/ai4r-wheels/workswarm_tui-*.whl \
    && uv build --wheel --python /opt/venv/bin/python --offline --no-cache --no-build-isolation --no-build-logs --out-dir /opt/ai4r-wheels \
    && uv pip install --python /opt/venv/bin/python --offline --no-deps --reinstall /opt/ai4r-wheels/workswarm-*.whl
COPY scripts/research_compat_wheel.py /tmp/research_compat_wheel.py
RUN python /tmp/research_compat_wheel.py --output /opt/ai4r-wheels --license /opt/ai4r/LICENSE \
    && uv pip install --python /opt/venv/bin/python --offline --no-deps /opt/ai4r-wheels/jiuwenswarm-*.whl
COPY scripts/research_offline_assets.py /tmp/research_offline_assets.py
RUN python /tmp/research_offline_assets.py --wheelhouse /opt/ai4r-wheels --project /opt/ai4r/pyproject.toml --lock /opt/ai4r/uv.lock --generated-root /opt/ai4r/jiuwenswarm/channels/tui/frontend --output /usr/local/share/ai4r-wheel-assets.json
COPY deploy/m1/build_identity.py /tmp/build_identity.py
COPY deploy/m1/install_codex.py /tmp/install_codex.py
RUN python /tmp/install_codex.py
RUN python /tmp/build_identity.py --lock /opt/ai4r/uv.lock --project /opt/ai4r/pyproject.toml --source /opt/ai4r/jiuwenswarm --tui-source /opt/ai4r/packages/jiuwenswarm-tui/jiuwenswarm_tui --output /usr/local/share/ai4r-build-identity.json

FROM runtime-tools AS production
COPY --from=application-build /opt/venv/ /opt/venv/
COPY --from=application-build /opt/ai4r-wheels/ /usr/local/share/ai4r-wheels/
COPY --from=application-build /usr/local/share/ai4r-build-identity.json /usr/local/share/ai4r-build-identity.json
COPY --from=application-build /usr/local/share/ai4r-wheel-assets.json /usr/local/share/ai4r-wheel-assets.json
COPY --from=application-build /usr/local/bin/codex /usr/local/bin/codex
COPY --from=application-build /usr/local/share/ai4r-codex-runtime.json /usr/local/share/ai4r-codex-runtime.json
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY deploy/m1/entrypoint.sh /usr/local/bin/ai4r-entrypoint
RUN chmod 0755 /usr/local/bin/ai4r-entrypoint \
    && mkdir -p /var/lib/ai4r /var/lib/ai4r-accounts /run/ai4r /workspace/poc \
    && mkdir -p /run/ai4r-private-qa && chmod 0700 /run/ai4r-private-qa \
    && chown ai4r:ai4r /var/lib/ai4r /var/lib/ai4r-accounts /run/ai4r
ENV JIUWENSWARM_M1_PROFILE=1 FRONTEND_HOST=0.0.0.0 FRONTEND_PORT=5173
WORKDIR /var/lib/ai4r/native
EXPOSE 5173
ENTRYPOINT ["/usr/local/bin/ai4r-entrypoint"]

# Verification is independently buildable without the frontend stage. It
# contains visible tests, never private oracle assets or model credentials.
FROM dependencies AS verify
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY jiuwenswarm/ ./jiuwenswarm/
COPY tests/ /workspace/tests/
COPY scripts/ /workspace/scripts/
COPY pytest.ini .importlinter /workspace/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-default-groups --group test --extra codex --extra tui --no-editable
COPY deploy/m1/install_codex.py /tmp/install_codex.py
RUN python /tmp/install_codex.py
WORKDIR /workspace
ENV PYTHONPATH=/opt/ai4r
CMD ["python", "-m", "pytest", "tests/unit_tests/research", "-q"]
