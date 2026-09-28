FROM python:3.11.16-slim@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e

RUN groupadd -r geoloop && useradd -r -g geoloop -d /app geoloop

WORKDIR /app

COPY pyproject.toml requirements.lock ./
COPY geoloop/ ./geoloop/

RUN pip install --no-cache-dir -r requirements.lock && \
    pip install --no-cache-dir --no-deps . && \
    mkdir -p /app/data && chown -R geoloop:geoloop /app

COPY scripts/entrypoint.sh /entrypoint.sh

USER geoloop

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-c", "from geoloop.main import run; run()"]
