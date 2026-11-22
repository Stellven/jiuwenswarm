FROM docker.io/library/python@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30
COPY payload/server.py /app/server.py
USER 65532:65532
ENTRYPOINT ["python","/app/server.py","--host","0.0.0.0","--port","8080"]
