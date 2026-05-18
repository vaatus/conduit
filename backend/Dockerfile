# SPDX-License-Identifier: MIT
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
COPY conduit /app/conduit
COPY tests /app/tests

RUN pip install --no-cache-dir .

EXPOSE 8001

CMD ["uvicorn", "conduit.main:app", "--host", "0.0.0.0", "--port", "8001"]
