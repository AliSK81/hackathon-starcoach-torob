# StarCoach image. The DB is not inside the image: mount a volume at /data (see docker-compose.yml).
# In Iran, Docker Hub and PyPI may be blocked (F24); pass mirrors, e.g.
#   --build-arg BASE_IMAGE=docker-mirror.liara.ir/library/python:3.12-slim
#   --build-arg PIP_INDEX_URL=https://package-mirror.liara.ir/repository/pypi/simple
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    STARCOACH_HOST=0.0.0.0 \
    STARCOACH_PORT=8000 \
    STARCOACH_DATA_DIR=/data/torob-dataset \
    STARCOACH_DB=/data/starcoach.db \
    STARCOACH_LOG_DIR=/data/logs

WORKDIR /app
COPY pyproject.toml README.md ./
COPY starcoach ./starcoach
RUN pip install . && useradd --create-home --uid 1000 app && mkdir -p /data && chown app /data

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=4).status == 200 else 1)"
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["starcoach", "serve"]
