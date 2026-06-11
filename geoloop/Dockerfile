FROM python:3.11-slim

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
