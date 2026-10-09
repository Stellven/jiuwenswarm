FROM node:22.12.0-bookworm-slim AS build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build
ARG CODEX_VERSION=0.162.0-alpha.2
RUN npm install --prefix /opt/codex --save-exact --ignore-scripts @openai/codex@${CODEX_VERSION}
RUN node -e 'const fs=require("node:fs"),path=require("node:path"); const arch={x64:"x86_64",arm64:"aarch64"}[process.arch]; if(!arch) throw new Error("Unsupported native Codex architecture"); const root=path.dirname(require.resolve("@openai/codex-linux-"+process.arch+"/package.json",{paths:["/opt/codex/node_modules"]})); fs.copyFileSync(path.join(root,"vendor",arch+"-unknown-linux-musl","bin","codex"),"/opt/codex/codex"); fs.chmodSync("/opt/codex/codex",0o755);'
RUN /opt/codex/codex --version

FROM python:3.13.1-slim-bookworm
COPY --from=build /opt/codex /opt/codex
WORKDIR /app
COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home compiler
COPY intent_compiler/ ./intent_compiler/
COPY --from=build /build/frontend/dist/ ./frontend/dist/
RUN mkdir -p /state /model-home /inputs/docs && chown -R compiler:compiler /state /model-home /inputs
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 INTENT_CONTAINER=1 INTENT_HOST=0.0.0.0 PORT=5173
ENV INTENT_STATE_DIR=/state INTENT_INPUT_ROOT=/inputs INTENT_INPUT_DIRECTORY=/inputs/docs
ENV CODEX_HOME=/model-home INTENT_CODEX_PATH=/opt/codex/codex
USER compiler
EXPOSE 5173
ENTRYPOINT ["python", "-m", "intent_compiler", "serve"]
