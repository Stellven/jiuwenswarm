FROM node:22-bookworm-slim AS frontend
WORKDIR /source
COPY . .
WORKDIR /source/jiuwenswarm/channels/web/frontend
RUN npm ci && npm run build

FROM python:3.11-slim-bookworm
RUN useradd --create-home --uid 10001 trial
WORKDIR /app
COPY deploy/intent-trial/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY jiuwenswarm /app/jiuwenswarm
COPY tests/fixtures/ai4research/intent/characterization/locked-candidates.json /app/characterization/locked-candidates.json
COPY --from=frontend /source/jiuwenswarm/channels/web/frontend/dist /app/jiuwenswarm/channels/web/frontend/dist
RUN mkdir -p /state /workspace && chown trial:trial /state /workspace && chmod 700 /state
USER trial
ENV PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-m", "jiuwenswarm.ai4research.service", "--state-dir", "/state", "--workspace", "/workspace"]
