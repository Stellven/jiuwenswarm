# simlab-runner: SIMLAB runner, executors, tools and check groups (PAS-M1 phase 1).
# Rebuilt from uv.lock only (X1.6). Base images are pinned by digest.
FROM ghcr.io/astral-sh/uv:0.5.9@sha256:ba36ea627a75e2a879b7f36efe01db5a24038f8d577bd7214a6c99d5d4f4b20c AS uv

FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
COPY --from=uv /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/simlab/.venv \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    SIMLAB_DATA_DIR=/data \
    PATH=/opt/simlab/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

WORKDIR /opt/simlab
# Dependencies first (cached layer), exactly as locked.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --python /usr/local/bin/python3.12
# Then SIMLAB itself, its tests, tools and benchmark cases.
COPY src/ src/
COPY tests/ tests/
COPY tools/ tools/
COPY benchmarks/simlab_bench/ benchmarks/simlab_bench/
RUN uv sync --frozen --python /usr/local/bin/python3.12 \
 && python -m simlab.build_identity --write /usr/local/share/simlab-build.json \
 && useradd --uid 11100 --create-home --home-dir /home/simlab --shell /usr/sbin/nologin simlab \
 && mkdir -p /data && chown simlab:simlab /data

USER simlab
VOLUME ["/data"]
ENTRYPOINT ["simlab"]
CMD ["serve"]
