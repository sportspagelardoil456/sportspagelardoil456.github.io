# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
#
# Slack ↔ WxO MCP Gateway — IBM Code Engine / container image
# Build (from this directory):
#   podman build -t slack-wxo-gateway:latest .
#   docker  build -t slack-wxo-gateway:latest .

FROM python:3.12-slim

LABEL maintainer="Markus van Kempen <mvankempen@ca.ibm.com>"
LABEL org.opencontainers.image.authors="Markus van Kempen <mvankempen@ca.ibm.com>, Markus van Kempen <markus.van.kempen@gmail.com>"
LABEL org.opencontainers.image.url="https://markusvankempen.github.io/"
LABEL org.opencontainers.image.source="https://github.com/markusvankempen/slack-wxo-mcp-gateway"
LABEL org.opencontainers.image.title="slack-wxo-gateway"
LABEL org.opencontainers.image.description="Slack ↔ watsonx Orchestrate MCP gateway"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GATEWAY_HOST=0.0.0.0 \
    GATEWAY_PORT=8080 \
    PORT=8080 \
    GATEWAY_CONFIG=/tmp/slack_mcp_gateway_config.yaml
# Set GATEWAY_ADMIN_USER + GATEWAY_ADMIN_PASSWORD at deploy time (Code Engine secret).

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Package layout: /app/slack_mcp_gateway/...
COPY . /app/slack_mcp_gateway/

# Seed default config into the image (runtime may override via env / volume)
RUN cp /app/slack_mcp_gateway/config.example.yaml /app/slack_mcp_gateway/config.yaml \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

# Code Engine injects PORT; server.py honors PORT then GATEWAY_PORT.
CMD ["python", "-m", "slack_mcp_gateway"]
