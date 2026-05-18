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
COPY conduit_mcp /app/conduit_mcp

RUN pip install --no-cache-dir .

# Default transport: streamable HTTP on 8765. Override CMD to use stdio.
EXPOSE 8765
ENV CONDUIT_BACKEND_URL=http://backend:8001
ENV MCP_TRANSPORT=http
ENV MCP_HTTP_PORT=8765

CMD ["python", "-m", "conduit_mcp.server"]
