# syntax=docker/dockerfile:1.7

FROM python:3.14-slim

ARG SUPERCRONIC_VERSION=v0.2.38
ARG TARGETARCH=amd64

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl util-linux \
    && rm -rf /var/lib/apt/lists/*

RUN case "${TARGETARCH}" in \
        amd64|arm64) ;; \
        *) echo "Unsupported TARGETARCH: ${TARGETARCH}" && exit 1 ;; \
    esac \
    && curl -fsSL "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-${TARGETARCH}" -o /usr/local/bin/supercronic \
    && chmod +x /usr/local/bin/supercronic

COPY pyproject.toml README.md ./
COPY app ./app
COPY sql ./sql

RUN pip install --upgrade pip \
    && pip install .

COPY docker/api-entrypoint.sh /usr/local/bin/api-entrypoint.sh
COPY docker/worker-entrypoint.sh /usr/local/bin/worker-entrypoint.sh
COPY docker/run-locked-job.sh /usr/local/bin/run-locked-job.sh

RUN chmod +x /usr/local/bin/api-entrypoint.sh /usr/local/bin/worker-entrypoint.sh /usr/local/bin/run-locked-job.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/api-entrypoint.sh"]
CMD ["polymarket-scanner-api"]
