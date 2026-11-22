# linux/amd64 manifest resolved from docker.io/library/python:3.12-slim
# on 2026-11-04. The local build is currently blocked; see container/probe-report.json.
FROM python@sha256:1148dbb014615300fa7e713b2f94f550c0d1c69780c0805f84f093ceee34dd0b
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY tool.py /cc/bundle/tool.py
CMD ["python", "/cc/bundle/tool.py"]
