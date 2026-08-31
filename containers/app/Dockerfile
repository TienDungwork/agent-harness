ARG Creanova_BUILD_VERSION=dev
FROM node:26.8-trixie-slim AS frontend-builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
RUN npm run build

FROM python:3.13.7-slim-trixie AS base
FROM base AS backend-builder

WORKDIR /app
ENV PYTHONPATH='/app'

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Pin Poetry version to match the version used to generate poetry.lock
ARG POETRY_VERSION=2.3.4
RUN apt-get update -y \
    && apt-get install -y curl make git build-essential jq gettext \
    && python3 -m pip install "poetry==${POETRY_VERSION}" --break-system-packages

COPY pyproject.toml poetry.lock ./
# Creanova-* packages are not on PyPI; install from vendored SDK paths.
COPY software-agent-sdk/Creanova-sdk ./software-agent-sdk/Creanova-sdk
COPY software-agent-sdk/Creanova-tools ./software-agent-sdk/Creanova-tools
COPY software-agent-sdk/Creanova-agent-server ./software-agent-sdk/Creanova-agent-server
RUN touch README.md
RUN export POETRY_CACHE_DIR \
    && poetry install --no-root \
    && rm -rf $POETRY_CACHE_DIR

FROM base AS Creanova-app

WORKDIR /app

# re-declare for this section
ARG Creanova_BUILD_VERSION

ENV RUN_AS_Creanova=true
# A random number--we need this to be different from the user's UID on the host machine
ENV Creanova_USER_ID=42420
ENV SANDBOX_LOCAL_RUNTIME_URL=http://host.docker.internal
ENV USE_HOST_NETWORK=false
ENV WORKSPACE_BASE=/opt/workspace_base
ENV Creanova_BUILD_VERSION=$Creanova_BUILD_VERSION
ENV SANDBOX_USER_ID=0
ENV FILE_STORE=local
ENV FILE_STORE_PATH=/.Creanova
ENV INIT_GIT_IN_EMPTY_WORKSPACE=1
RUN mkdir -p $FILE_STORE_PATH
RUN mkdir -p $WORKSPACE_BASE

RUN apt-get update -y \
    && apt-get install -y curl git ssh sudo \
    && rm -rf /var/lib/apt/lists/*

# Default is 1000, but OSX is often 501
RUN sed -i 's/^UID_MIN.*/UID_MIN 499/' /etc/login.defs
# Default is 60000, but we've seen up to 200000
RUN sed -i 's/^UID_MAX.*/UID_MAX 1000000/' /etc/login.defs

RUN groupadd --gid $Creanova_USER_ID Creanova
RUN useradd -l -m -u $Creanova_USER_ID --gid $Creanova_USER_ID -s /bin/bash Creanova && \
    usermod -aG Creanova Creanova && \
    usermod -aG sudo Creanova && \
    echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
RUN chown -R Creanova:Creanova /app && chmod -R 770 /app
RUN sudo chown -R Creanova:Creanova $WORKSPACE_BASE && sudo chmod -R 770 $WORKSPACE_BASE
USER Creanova

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH='/app'

COPY --chown=Creanova:Creanova --chmod=770 --from=backend-builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Pin pip to a known-good version (reproducible builds) and fix CVE-2025-8869
# Pin both venv pip and system pip (Trivy scans both)
# - `python -m pip` uses the venv because `PATH` is prefixed with `${VIRTUAL_ENV}/bin`
# - `/usr/local/bin/python3 -m pip` uses the system interpreter regardless of `PATH`
ARG PIP_VERSION=26.0.1
RUN python -m pip install --no-cache-dir "pip==${PIP_VERSION}"

USER root
RUN /usr/local/bin/python3 -m pip install --no-cache-dir "pip==${PIP_VERSION}" --break-system-packages
USER Creanova

COPY --chown=Creanova:Creanova --chmod=770 ./skills ./skills
COPY --chown=Creanova:Creanova --chmod=770 ./Creanova ./Creanova
COPY --chown=Creanova:Creanova pyproject.toml poetry.lock README.md MANIFEST.in LICENSE ./

# Add this line to set group ownership of all files/directories not already in "app" group
# Creanova:Creanova -> Creanova:Creanova
RUN find /app \! -group Creanova -exec chgrp Creanova {} +

COPY --chown=Creanova:Creanova --chmod=770 --from=frontend-builder /app/build ./frontend/build
COPY --chown=Creanova:Creanova --chmod=770 ./containers/app/entrypoint.sh /app/entrypoint.sh

USER root

WORKDIR /app

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "Creanova.server.listen:app", "--host", "0.0.0.0", "--port", "3000"]
