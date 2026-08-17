# syntax=docker/dockerfile:1.7

# ═══════════════════════════════════════════════════════════════════════════════
# agent-canvas all-in-one Docker image
#
# Combines three services into a single image:
#   1. Agent Server  — from ghcr.io/Creanova/agent-server (upstream SDK image)
#   2. Automation    — installed via pip from Creanova-automation
#   3. Frontend      — agent-canvas static build served by Node.js
#
# The entrypoint starts all three services and an ingress proxy that unifies
# them behind a single port (default 8000):
#   /api/automation/*  → automation backend (:18001)
#   /api/*, /sockets   → agent server (:18000)
#   /* (default)       → static frontend + SPA fallback
# ═══════════════════════════════════════════════════════════════════════════════

# ── Build args ────────────────────────────────────────────────────────────────
# No hardcoded defaults — values are derived from config/defaults.json.
# CI passes these via --build-arg; for local builds use:
#   node scripts/docker-build.mjs          (recommended, reads JSON for you)
#   docker build --build-arg AGENT_SERVER_IMAGE=... --build-arg AUTOMATION_VERSION=... -f docker/Dockerfile .
ARG AGENT_SERVER_IMAGE
ARG AUTOMATION_VERSION

# ── Stage 1: Build frontend ──────────────────────────────────────────────────
FROM node:24-slim AS frontend-build

WORKDIR /build

# Cache-friendly: package files first
COPY package.json package-lock.json ./
RUN npm ci

# Copy everything needed for the build
COPY . .

# Build the static frontend.
# VITE_POSTHOG_API_KEY is a public client key baked into the bundle. CI passes
# production for tagged releases and staging for PR/main images.
# VITE_BASE_PATH is baked into React Router/Vite so the Docker image serves
# Canvas under the Cloud subpath instead of a dedicated hostname.
ARG VITE_POSTHOG_API_KEY=""
ARG VITE_BASE_PATH="/canvas"
ENV VITE_POSTHOG_API_KEY=${VITE_POSTHOG_API_KEY}
ENV VITE_BASE_PATH=${VITE_BASE_PATH}
RUN npm run build

# ── Stage 1b: Generate shell-sourceable defaults from config/defaults.json ──
# This avoids needing jq/python at container runtime to parse the JSON.
FROM node:24-slim AS config-gen
COPY config/defaults.json /tmp/
RUN node -e " \
  const c = JSON.parse(require('fs').readFileSync('/tmp/defaults.json','utf-8')); \
  const lines = [ \
    'CONFIG_AGENT_SERVER_PORT=' + c.ports.agentServer, \
    'CONFIG_AUTOMATION_PORT=' + c.ports.automation, \
    'CONFIG_PROXY_PORT=' + c.ports.proxy, \
    'CONFIG_STATE_SUBDIR=' + c.paths.stateSubdir, \
    'CONFIG_CONVERSATIONS=' + c.paths.conversations, \
    'CONFIG_BASH_EVENTS=' + c.paths.bashEvents, \
    'CONFIG_AUTOMATION_DB=' + c.paths.automationDb, \
    'CONFIG_CANVAS_BASE_PATH=' + c.paths.canvasBasePath, \
  ]; \
  require('fs').writeFileSync('/tmp/defaults.env', lines.join('\n') + '\n'); \
"

# ── Stage 2: Combined image ──────────────────────────────────────────────────
FROM ${AGENT_SERVER_IMAGE} AS final

ARG AUTOMATION_VERSION
ARG AGENT_SERVER_SDK_GIT_REF=""
ARG Creanova_BUILD_GIT_SHA=unknown
ARG Creanova_BUILD_GIT_REF=unknown
ARG VITE_BASE_PATH="/canvas"

ARG AGENT_CANVAS_VERSION=dev
LABEL org.opencontainers.image.title="agent-canvas"
LABEL org.opencontainers.image.description="All-in-one agent-canvas: Agent Server + Automation + Frontend"
LABEL org.opencontainers.image.source="https://github.com/Creanova/agent-canvas"
LABEL org.opencontainers.image.version="${AGENT_CANVAS_VERSION}"
LABEL org.opencontainers.image.revision="${Creanova_BUILD_GIT_SHA}"

ENV AGENT_CANVAS_BUILD_GIT_SHA=${Creanova_BUILD_GIT_SHA}
ENV AGENT_CANVAS_BUILD_GIT_REF=${Creanova_BUILD_GIT_REF}
ENV AGENT_CANVAS_BASE_PATH=${VITE_BASE_PATH}

USER root

# Install system deps required by automation's transitive dependencies
# (asyncpg needs libpq, which the agent-server base image may not include).
RUN if command -v apt-get >/dev/null 2>&1; then \
      apt-get update && \
      apt-get install -y --no-install-recommends libpq-dev && \
      rm -rf /var/lib/apt/lists/*; \
    fi

# Install automation server via pip.
# Shared deps (Creanova-sdk, fastapi, uvicorn, pydantic, httpx, …) are
# already satisfied by the agent-server base image, so only automation-
# specific packages (asyncpg, sqlalchemy, boto3, gcloud, …) are added.
RUN uv pip install --system "Creanova-automation==${AUTOMATION_VERSION}" 2>/dev/null \
    || pip install --no-cache-dir "Creanova-automation==${AUTOMATION_VERSION}"

RUN if [ -n "${AGENT_SERVER_SDK_GIT_REF}" ]; then \
      BASE_GIT_URL="git+https://github.com/Creanova/software-agent-sdk@${AGENT_SERVER_SDK_GIT_REF}" && \
      uv pip install --system --force-reinstall \
        "${BASE_GIT_URL}#subdirectory=Creanova-sdk" \
        "${BASE_GIT_URL}#subdirectory=Creanova-tools" \
        "${BASE_GIT_URL}#subdirectory=Creanova-workspace"; \
    fi

# Copy the frontend build output.
# react-router.config.ts unpacks build/client/ into build/ for non-Vercel builds.
COPY --from=frontend-build /build/build /opt/agent-canvas/frontend

# Copy the static-server scripts and their production runtime deps.
COPY scripts/static-server.mjs /opt/agent-canvas/static-server.mjs
COPY scripts/proxy-utils.mjs /opt/agent-canvas/proxy-utils.mjs
COPY --from=frontend-build /build/node_modules/httpxy /opt/agent-canvas/node_modules/httpxy
COPY --from=frontend-build /build/node_modules/sirv /opt/agent-canvas/node_modules/sirv
COPY --from=frontend-build /build/node_modules/@polka /opt/agent-canvas/node_modules/@polka
COPY --from=frontend-build /build/node_modules/mrmime /opt/agent-canvas/node_modules/mrmime
COPY --from=frontend-build /build/node_modules/totalist /opt/agent-canvas/node_modules/totalist

# Copy the runtime-services-info builder (entrypoint.sh runs it as a CLI to
# emit the agent's <RUNTIME_SERVICES> block; same builder the dev stack uses).
COPY scripts/runtime-services-info.mjs /opt/agent-canvas/runtime-services-info.mjs

# Persisted conversations created before the client_tools migration still
# import canvas_ui_tool by qualname. Keep the compatibility module available;
# new conversations define canvas_ui_control through a JSON client tool.
COPY tools/ /opt/agent-canvas/tools/

# Copy generated defaults.env (from config/defaults.json via config-gen stage)
COPY --from=config-gen /tmp/defaults.env /opt/agent-canvas/defaults.env

# Copy the entrypoint
COPY docker/entrypoint.sh /opt/agent-canvas/entrypoint.sh
RUN chmod +x /opt/agent-canvas/entrypoint.sh

# Pre-create persistence directories with correct ownership so the
# Creanova user can write to them even when Docker creates anonymous
# volumes (which default to root).
RUN mkdir -p /home/Creanova/.Creanova/agent-canvas/conversations \
             /home/Creanova/.Creanova/agent-canvas/bash_events \
             /home/Creanova/.Creanova/automation \
             /projects && \
    chown -R Creanova:Creanova /home/Creanova/.Creanova /projects

USER Creanova

# Persistence volumes:
#   /home/Creanova/.Creanova — settings, secrets, conversations, automation DB
#   /projects                  — user code the agent can read/edit
# Bind-mount these for data to survive container restarts:
#   docker run -v ~/.Creanova:/home/Creanova/.Creanova -v ~/projects:/projects ...
VOLUME ["/home/Creanova/.Creanova", "/projects"]

# The entrypoint starts all services and the ingress proxy.
# Port 8000 is the unified entry point.
EXPOSE 8000

ENTRYPOINT ["tini", "--", "/opt/agent-canvas/entrypoint.sh"]
