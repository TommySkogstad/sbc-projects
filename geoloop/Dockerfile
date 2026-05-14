FROM python:3.11-slim

RUN groupadd -r geoloop && useradd -r -g geoloop -d /app geoloop

WORKDIR /app

COPY pyproject.toml .
COPY geoloop/ ./geoloop/

RUN pip install --no-cache-dir . && \
    mkdir -p /app/data && chown -R geoloop:geoloop /app

COPY scripts/entrypoint.sh /entrypoint.sh

USER geoloop

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-c", "from geoloop.main import run; run()"]
