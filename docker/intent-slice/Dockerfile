# One native application service; generated research code is not executed here.
FROM node:22-bookworm-slim AS frontend
WORKDIR /app/jiuwenswarm/channels/web/frontend
COPY jiuwenswarm/channels/web/frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY . /app
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.12.5
COPY . .
RUN uv sync --locked --extra codex --no-dev
COPY --from=frontend /app/jiuwenswarm/channels/web/frontend/dist /app/jiuwenswarm/channels/web/frontend/dist
ENV PATH="/app/.venv/bin:${PATH}" \
    JIUWENSWARM_AGENT_SDK=codex_subscription \
    GATEWAY_HOST=127.0.0.1 WEB_HOST=127.0.0.1 AGENT_SERVER_HOST=127.0.0.1
EXPOSE 5173
ENTRYPOINT ["python", "-m", "jiuwenswarm.ai4research.intent.launch", "--no-browser"]
