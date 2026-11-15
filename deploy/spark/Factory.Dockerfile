# build-factory.sh checks this existing local image's immutable ID before build.
FROM ai4r-hybrid-runner:20261026 AS runtime
USER root
COPY deploy/spark/requirements-runtime.txt /tmp/factory-requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/factory-requirements.txt && rm /tmp/factory-requirements.txt
WORKDIR /factory
COPY jiuwenswarm/factory/ /factory/jiuwenswarm/factory/
COPY jiuwenswarm/ccv2/ /factory/jiuwenswarm/ccv2/
COPY deploy/spark/ /factory/deploy/spark/
ENV PYTHONPATH=/factory
ENTRYPOINT ["python3", "-m", "jiuwenswarm.factory.cli"]

FROM runtime AS validation
COPY deploy/spark/requirements-test.txt /tmp/test-requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/test-requirements.txt && rm /tmp/test-requirements.txt
# Git is needed only by source-identity and historical Jetson regression fixtures.
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY tests/factory/ /factory/tests/factory/
