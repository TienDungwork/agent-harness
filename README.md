<a name="readme-top"></a>
<div align="center">
  <img src="https://assets.Creanova.dev/logo-whitebackground.png" alt="Creanova logo" width="340">
  <p align="center">
    <strong>The self-hosted developer control center for coding agents and automations.</strong>
  </p>
  <p align="center">
    Run Creanova, Claude Code, Codex, Gemini, or any ACP-compatible agent across local, remote, and cloud backends.
  </p>
</div>
<div align="center">
  <a href="https://github.com/Creanova/incubator-program"><img src="https://img.shields.io/badge/status-beta-blue?style=for-the-badge" alt="Project status beta"></a>
  <a href="https://github.com/Creanova/agent-canvas/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/Creanova/agent-canvas/ci.yml?branch=main&style=for-the-badge" alt="CI status"></a>
  <a href="https://www.npmjs.com/package/@Creanova/agent-canvas"><img src="https://img.shields.io/npm/v/%40Creanova%2Fagent-canvas?style=for-the-badge&logo=npm" alt="npm version"></a>
  <a href="https://docs.Creanova.dev/Creanova/usage/agent-canvas/backends"><img src="https://img.shields.io/badge/Documentation-000?logo=googledocs&logoColor=FFE165&style=for-the-badge" alt="Documentation"></a>
  <a href="https://go.Creanova.dev/slack"><img src="https://img.shields.io/badge/Slack-Join%20the%20community-611f69?logo=slack&logoColor=white&style=for-the-badge" alt="Join us on Slack"></a>
</div>
<div align="center">
  <a href="#quickstart">Quickstart</a> |
  <a href="https://docs.Creanova.dev/overview/introduction">Docs</a> |
  <a href="https://docs.Creanova.dev/Creanova/usage/agent-canvas/backend-setup/vm">Self-Hosting</a> |
  <a href="https://docs.Creanova.dev/Creanova/usage/agent-canvas/acp-agents">ACP Agents</a> |
  <a href="https://docs.Creanova.dev/Creanova/usage/agent-canvas/prebuilt-automations">Automations</a> |
  <a href="https://go.Creanova.dev/slack">Slack</a>
</div>
<p align="center">
  <img src="https://assets.Creanova.dev/screenshot/automation-preview.png" alt="Agent Canvas automation preview" width="100%">
</p>
<hr>

Creanova Agent Canvas turns your coding agents into a self-hosted, always-on engineering team. It's a developer control center for starting conversations and automating everyday tasks — like generating reports that publish to Slack or automatically decomposing GitHub issues into tasks.

It runs locally on your machine by default, but can connect to multiple “agent backends”, e.g. running agents in Docker containers, on VMs, or within your company infrastructure. You can optionally choose to run agents on Creanova Cloud or Creanova Enterprise infrastructure.

Agent Canvas runs the open source Creanova agent out-of-the-box, but can use any third-party agent like Claude Code and Codex.

|    |    |
|---|---|
| [**Self-host your way**](https://docs.Creanova.dev/Creanova/usage/agent-canvas/backend-setup/vm) | Run agents locally, in Docker, on VMs, or anywhere you can run an agent server backend |
| [**Switch between different backends**](https://docs.Creanova.dev/Creanova/usage/agent-canvas/backends) | Switch between local, remote, and cloud agents without losing focus |
| [**Create automations**](https://docs.Creanova.dev/Creanova/usage/agent-canvas/prebuilt-automations) | Create automations and workflows that integrate with Slack, GitHub, Linear, and more. Run on a schedule or in response to webhook events  |
| [**Integrate with the tools you use**](https://docs.Creanova.dev/Creanova/usage/agent-canvas/prebuilt-automations) | Connect your automations with third-party services like Slack, GitHub, Notion, and more to automate workflows |
| [**Bring your own model**](https://docs.Creanova.dev/Creanova/usage/settings/llm-settings#llm-profiles) | Use with any LLM |
| [**Use with any agent**](https://docs.Creanova.dev/Creanova/usage/agent-canvas/acp-agents) | Use with Creanova, Claude Code, Codex, Gemini, or any agent with Agent-Client Protocol (ACP). |


If you have questions or feedback, please open a GitHub issue or join the [#proj-agent-canvas channel in Slack](https://Creanova.dev/joinslack).

> [!NOTE]
> The code in this repo is moving! See [Agent Canvas transition FAQ](https://github.com/Creanova/Creanova/issues/14841)
>
> The source code for Creanova Agent and Agent Server lives in [Creanova/software-agent-sdk](https://github.com/Creanova/software-agent-sdk).
>
> The source code for Agent Canvas lives in [Creanova/agent-canvas](https://github.com/Creanova/agent-canvas).

## Table of Contents

- [Quickstart](#quickstart)
- [Local Development](#local-development)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Variables & Configuration](#environment-variables--configuration)
  - [Running the Application](#running-the-application)
    - [Full Stack (Backend + Frontend)](#full-stack-backend--frontend)
    - [Backend Only](#backend-only)
    - [Frontend Only](#frontend-only)
  - [Local URLs](#local-urls)
  - [Troubleshooting Notes](#troubleshooting-notes)
- [Docker Deployment](#docker-deployment)
  - [Docker Compose](#docker-compose)
  - [Pre-built Container Image](#pre-built-container-image)
  - [Dev Container](#dev-container)
- [Architecture](#architecture)
- [More Documentation](#more-documentation)

---

## Quickstart

You can install Creanova to run agents on any machine: on your laptop, on a dedicated computer like a Mac Mini,
or on a server in the cloud.

The most powerful way to run Creanova is on a server in the cloud. This allows your agents to continue running
even when your laptop is shut, and makes it easier to trigger your agents through third-party services
like Slack, GitHub, and Datadog. See the [self-hosting guide](https://docs.Creanova.dev/Creanova/usage/agent-canvas/backend-setup/vm) for details, especially with respect to security hardening.

Notably, you can run the backend in _multiple different environments_, and switch between
them from the same Agent Canvas frontend. E.g. you can share an Agent Server with your team for agents doing
code review and dependency updates, then have your personal agents running on your laptop.

### Option 1: Global CLI (Without a Sandbox)

> [!WARNING]
> This runs the agent-server directly on the machine you're installing on — the agent will have full access to your filesystem!

**Prerequisites**: Node.js 22.12.x or later, `uv`

```sh
npm install -g @Creanova/agent-canvas
agent-canvas
```

The `agent-canvas` command starts the full local stack by default. You can also split it when you want to run pieces separately:

```sh
agent-canvas --frontend-only  # static frontend + ingress only
agent-canvas --backend-only   # agent server + automation backend + ingress only
```

### Option 2: With a Docker Sandbox

**Prerequisites**:
- Docker (Docker Desktop on macOS/Windows, or Docker Engine on Linux).
- A host directory for `PROJECTS_PATH` containing the project folders you want the agent to access.

**macOS / Linux:**

```sh
export PROJECTS_PATH="$HOME/projects"  # directory containing your project folders
mkdir -p "$PROJECTS_PATH" "$HOME/.Creanova"

docker run -it --rm \
  -p 8000:8000 \
  -v "$HOME/.Creanova:/home/Creanova/.Creanova" \
  -v "${PROJECTS_PATH}:/projects" \
  ghcr.io/Creanova/agent-canvas:1
```

**Windows (PowerShell / Windows Terminal):** See [README.windows.md](https://github.com/Creanova/agent-canvas/blob/main/README.windows.md) for the equivalent commands.

---

## Local Development

Follow these steps to set up and run the full Creanova codebase (Python backend + React frontend) locally from source.

### Prerequisites

Ensure you have the following installed on your machine:

| Tool | Version / Requirement | Purpose |
| ---- | --------------------- | ------- |
| **Python** | `3.12.x` or `3.13.x` (`>= 3.12, < 3.14`) | Backend runtime and services |
| **Poetry** | `>= 1.8.0` | Python package and environment management |
| **Node.js** | `>= 22.12.0` | Frontend runtime |
| **npm** | Bundled with Node.js | Frontend package management |
| **Docker** | Docker Engine or Docker Desktop | Sandbox execution and containerized deployment |
| **netcat (`nc`)** | `netcat-openbsd` or equivalent | Readiness checks during local startup |
| **tmux** | Recommended | Terminal session handling in local runtime |

#### OS-Specific Dependency Installation

<details>
<summary><strong>macOS (Homebrew)</strong></summary>

```bash
brew install python@3.12 node poetry netcat
brew install --cask docker
```
In Docker Desktop: **Settings → Advanced → Enable "Allow the default Docker socket to be used"**.
</details>

<details>
<summary><strong>Linux (Ubuntu / Debian)</strong></summary>

```bash
sudo apt update
sudo apt install -y build-essential curl netcat-openbsd software-properties-common tmux

# Python 3.12
sudo apt install -y python3.12 python3.12-dev python3.12-venv

# Node.js 22.x
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Poetry
curl -sSL https://install.python-poetry.org | python3 -
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Docker Engine & Docker Compose plugin
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```
*(Log out and back in after adding your user to the `docker` group).*
</details>

<details>
<summary><strong>Windows (WSL2)</strong></summary>

1. Install WSL2 with Ubuntu 22.04+: `wsl --install -d Ubuntu-22.04`
2. Follow the Linux setup steps inside your WSL Ubuntu terminal.
3. In Docker Desktop for Windows: enable **WSL 2 based engine** and toggle **WSL Integration** for your Ubuntu distro.
4. Always clone and run the repository inside the WSL Linux filesystem (`~/...`), not on `/mnt/c/`.
</details>

---

### Installation

Clone the repository and build the project dependencies:

```bash
# Clone the repository
git clone https://github.com/Creanova/agent-harness.git
cd agent-harness

# Build Python and Frontend dependencies, pre-commit hooks, and assets
make build
```

The `make build` command automatically:
1. Validates system dependencies (Python, Node.js, npm, Poetry, Docker).
2. Installs Python packages via `poetry install --with dev,test,runtime`.
3. Installs Frontend packages in `frontend/` via `npm install`.
4. Configures Git pre-commit hooks.
5. Builds the frontend production bundle.

#### Individual Install Commands (Optional)

If you prefer to install components separately:

```bash
# Install backend Python dependencies only
poetry install --with dev,test,runtime

# Install frontend dependencies only
cd frontend && npm install && cd ..

# Install pre-commit hooks
make install-pre-commit-hooks
```

---

### Environment Variables & Configuration

#### 1. Core Configuration (`config.toml`)
Creanova uses a root `config.toml` file for workspace paths and LLM settings.

To initialize an interactive configuration prompt:
```bash
make setup-config
```

Or generate a basic configuration:
```bash
make setup-config-basic
```

Key fields in `config.toml`:
```toml
[core]
workspace_base = "./workspace"
debug = false

[llm]
model = "gpt-4o"
api_key = "your-api-key"
# base_url = "http://localhost:11434/v1" # For local Ollama / LiteLLM
```

> [!TIP]
> When using the Web UI, you can also configure your LLM provider, models, and API keys directly under the **Settings** page (`/settings`).

#### 2. Backend & Runtime Environment Variables

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `RUNTIME` | Execution runtime (`docker` for container sandboxing, `local` for host execution) | `docker` |
| `INSTALL_DOCKER` | Set to `0` when running locally without Docker daemon verification | `1` |
| `BACKEND_HOST` | Host IP for backend server binding | `127.0.0.1` |
| `BACKEND_PORT` | Port for backend REST and WebSocket server | `3000` |
| `FRONTEND_HOST` | Host IP for frontend dev server binding | `127.0.0.1` |
| `FRONTEND_PORT` | Port for frontend dev server | `3001` |
| `WORKSPACE_BASE` | Absolute or relative path to agent workspace directory | `./workspace` |
| `DEBUG` | Set `1` to enable verbose LLM interaction logging under `logs/llm/` | `0` |
| `PLAYWRIGHT_BROWSERS_PATH` | Cache path for Playwright Chromium binaries | `~/.cache/playwright` |

#### 3. Frontend Environment Variables (`frontend/.env`)

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `VITE_BACKEND_HOST` | Backend host & port used for HTTP API requests | `127.0.0.1:3000` |
| `VITE_BACKEND_BASE_URL` | Hostname without protocol used for WebSocket connections | `localhost:3000` |
| `VITE_FRONTEND_PORT` | Port for Vite frontend dev server | `3001` |
| `VITE_MOCK_API` | Enable/disable Mock Service Worker (MSW) mocking | `false` |
| `VITE_MOCK_SAAS` | Simulate SaaS multi-tenant UI mode | `false` |
| `VITE_USE_TLS` | Enable HTTPS / WSS for backend connections | `false` |
| `VITE_INSECURE_SKIP_VERIFY`| Skip TLS certificate verification | `false` |

---

### Running the Application

#### Full Stack (Backend + Frontend)

Start both backend and frontend servers with a single command:

```bash
# Standard run (Backend on :3000, Frontend on :3001)
make run
```

To run with custom ports or allow external/cloud network access:
```bash
make run FRONTEND_PORT=12000 FRONTEND_HOST=0.0.0.0 BACKEND_HOST=0.0.0.0
```

To run locally in host mode without Docker containers:
```bash
export INSTALL_DOCKER=0
export RUNTIME=local
make run
```

#### Backend Only

To run just the Python FastAPI/Uvicorn backend:

```bash
make start-backend
```
*Backend runs on `http://127.0.0.1:3000` with hot reload enabled.*

Alternatively, run directly with Poetry:
```bash
poetry run uvicorn Creanova.server.listen:app --host 127.0.0.1 --port 3000 --reload --reload-exclude "./workspace"
```

#### Frontend Only

To run just the React/Vite frontend:

```bash
# Using Makefile
make start-frontend

# Or directly from the frontend directory
cd frontend
npm run dev
```

Frontend development options:
```bash
cd frontend
npm run dev                  # Live backend mode
npm run dev:mock             # Mock API backend mode (MSW)
npm run dev:mock:saas        # Mock SaaS multi-tenant mode
npm run build && npm start   # Production build preview
```

---

### Local URLs

Once started, access the application through the following endpoints:

| Service | URL | Description |
| ------- | --- | ----------- |
| **Frontend Web App** | [http://localhost:3001](http://localhost:3001) | Main user interface for conversations and agent interaction |
| **Settings UI** | [http://localhost:3001/settings](http://localhost:3001/settings) | LLM provider, model selection, and API key management |
| **Backend REST API** | [http://localhost:3000](http://localhost:3000) | Application server REST endpoints and WebSocket server |
| **Interactive API Docs (Swagger)** | [http://localhost:3000/docs](http://localhost:3000/docs) | Swagger UI for exploring and testing API endpoints |
| **Alternative API Docs (ReDoc)** | [http://localhost:3000/redoc](http://localhost:3000/redoc) | OpenAPI specification rendered with ReDoc |

---

### Troubleshooting Notes

- **`nc: command not found` on startup:**
  The `make run` target uses netcat to wait for the backend socket. Install it via `sudo apt install -y netcat-openbsd` (Ubuntu/Debian) or `brew install netcat` (macOS).

- **Stale tmux session (`duplicate session: test-session`):**
  If local runtime startup crashes with a duplicate session error, terminate the stale session:
  ```bash
  tmux -S /tmp/tmux-$(id -u)/default kill-session -t test-session
  ```

- **Playwright Chromium missing in local runtime:**
  If browser-based tasks fail due to missing browser binaries, install Chromium into your user cache:
  ```bash
  PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/playwright poetry run playwright install chromium
  ```

- **401 Unauthorized in Settings UI:**
  If an inherited `SESSION_API_KEY` prevents access to `/api/v1/settings`, unset it in your shell before running:
  ```bash
  unset SESSION_API_KEY
  make run
  ```

- **Docker permission denied (`/var/run/docker.sock`):**
  Ensure your user is in the `docker` group (`sudo usermod -aG docker $USER`) and you have restarted your session, or grant permissions with `sudo chmod 666 /var/run/docker.sock`.

- **Port already in use (`EADDRINUSE` / `bind: address already in use`):**
  Check what process is occupying port 3000 or 3001 with `lsof -i :3000` or `lsof -i :3001`, or override ports via `make run BACKEND_PORT=3005 FRONTEND_PORT=3006`.

- **WSL filesystem lag:**
  Ensure the repository is placed in the Linux filesystem (e.g. `~/Creanova`) and not on Windows mounts (`/mnt/c/...`).

---

## Docker Deployment

### Docker Compose

Deploy the containerized Creanova stack using Docker Compose:

```bash
# Run with Docker Compose
docker compose up -d

# Or via Makefile target
make docker-run
```

#### Docker Compose Configuration
The `docker-compose.yml` mounts your local workspace and manages agent container sandboxes:
```bash
export WORKSPACE_BASE="$PWD/workspace"
export AGENT_SERVER_IMAGE_REPOSITORY="ghcr.io/Creanova/agent-server"
export AGENT_SERVER_IMAGE_TAG="1.30.0-python"
docker compose up -d
```
Access the containerized application at `http://localhost:13000`.

### Pre-built Container Image

Run the official all-in-one container directly:

```bash
export PROJECTS_PATH="$HOME/projects"
mkdir -p "$PROJECTS_PATH" "$HOME/.Creanova"

docker run -it --rm \
  -p 8000:8000 \
  -v "$HOME/.Creanova:/home/Creanova/.Creanova" \
  -v "${PROJECTS_PATH}:/projects" \
  ghcr.io/Creanova/agent-canvas:1
```
Access the application at `http://localhost:8000`.

### Dev Container

Develop inside an isolated container with all pre-configured runtimes:
```bash
make docker-dev
```
Or use VS Code with the Remote Containers extension: open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) and choose **Dev Containers: Reopen in Container**.

---

# Architecture

Agent Canvas is powered by the [Creanova Agent Server](https://github.com/Creanova/software-agent-sdk/tree/main/Creanova-agent-server/Creanova/agent_server), a REST API for running multiple agents on a single machine. Each Agent Server runs on a single host/port; the Agent Canvas can connect to multiple Agent Servers and easily flip between them.

You can run an Agent Server anywhere:

- Directly on your laptop (be careful!)
- On a dedicated machine like a Mac Mini
- On a virtual machine in the cloud
- Inside Creanova Cloud (our commercial offering)

The Agent Server is often paired with an [Automation Server](https://github.com/Creanova/automation), which lets you set up agents that run on a schedule or in response to events.

<img width="1456" height="1258" alt="image" src="https://github.com/user-attachments/assets/cb6de6f5-ac30-4d04-a76a-b5c259f0c163" />

## More documentation

- [Documentation index](https://docs.Creanova.dev/overview/introduction)
- [Architecture overview](#architecture)
- [Development guide](./Development.md)
- [Self-hosting guide](https://docs.Creanova.dev/Creanova/usage/agent-canvas/backend-setup/vm)

