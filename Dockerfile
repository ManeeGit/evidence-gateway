FROM python:3.15-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 EVIDENCE_DB=/data/evidence.db
WORKDIR /app
COPY pyproject.toml README.md LICENSE requirements-server.txt ./
COPY src ./src
COPY examples ./examples
RUN pip install --no-cache-dir . -r requirements-server.txt \
    && groupadd --gid 10001 gateway \
    && useradd --uid 10001 --gid gateway --no-create-home gateway \
    && mkdir /data && chown gateway:gateway /data
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"
CMD ["waitress-serve", "--call", "--listen=0.0.0.0:8080", "--threads=4", "--max-request-body-size=16384", "--channel-timeout=30", "evidence_gateway.api:from_environment"]
