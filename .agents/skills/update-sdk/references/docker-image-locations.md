# Docker Image Locations — Complete Inventory

Every file in the Creanova repository containing a hardcoded Docker image tag, repository, or version-pinned image reference. Organized by update cadence.

## Updated During SDK Bump (must change)

These files contain image tags that **must** be updated whenever the SDK version or pinned commit changes.

### `Creanova/app_server/sandbox/sandbox_spec_service.py`
- **Line:** `AGENT_SERVER_IMAGE = 'ghcr.io/Creanova/agent-server:<tag>-python'`
- **Format:** `<sdk-version>-python` for releases (e.g., `1.12.0-python`), `<7-char-commit-hash>-python` for dev pins
- **Source of truth** for which agent-server image the app server pulls at runtime
- **⚠️ Gotcha:** When pinning to an SDK PR, the image tag is the **merge-commit SHA** from GitHub Actions, not the PR head-commit SHA. Check the SDK PR description or CI logs for the correct tag.

### `docker-compose.yml`
- **Lines:**
  ```yaml
  - AGENT_SERVER_IMAGE_REPOSITORY=${AGENT_SERVER_IMAGE_REPOSITORY:-ghcr.io/Creanova/agent-server}
  - AGENT_SERVER_IMAGE_TAG=${AGENT_SERVER_IMAGE_TAG:-<tag>-python}
  ```
- Used by `docker compose up` for local development

### `containers/dev/compose.yml`
- **Lines:**
  ```yaml
  - AGENT_SERVER_IMAGE_REPOSITORY=${AGENT_SERVER_IMAGE_REPOSITORY:-ghcr.io/Creanova/agent-server}
  - AGENT_SERVER_IMAGE_TAG=${AGENT_SERVER_IMAGE_TAG:-<tag>-python}
  ```
- Used by the dev container setup
- **Known issue:** On main as of 1.4.0, this file still points to `ghcr.io/Creanova/runtime` instead of `agent-server`, and the tag is `1.2-nikolaik` (stale from the V0 era). The `check-version-consistency.yml` CI workflow catches this.

## Updated During Release Commit (version string only)

### `pyproject.toml`
- **Line:** `version = "X.Y.Z"` under `[tool.poetry]`
- The Python version is derived from this at runtime via `Creanova/version.py`

### `frontend/package.json`
- **Line:** `"version": "X.Y.Z"`

### `frontend/package-lock.json`
- **Two places:** root `"version": "X.Y.Z"` and `packages[""].version`

## Dynamic References (auto-derived, no manual update)

### `Creanova/version.py`
- Reads version from `pyproject.toml` at runtime → `Creanova.__version__`

### `.github/scripts/update_pr_description.sh`
- Uses `${SHORT_SHA}` variable at CI runtime, not hardcoded

### `enterprise/Dockerfile`
- `ARG BASE="ghcr.io/Creanova/Creanova"` — base image, version supplied at build time

## Image Registries

| Registry | Usage |
|----------|-------|
| `ghcr.io/Creanova/agent-server` | V1 agent-server (sandbox) — built by SDK repo CI |
| `ghcr.io/Creanova/Creanova` | Main app image — built by `ghcr-build.yml` |
| `docker.Creanova.dev/Creanova/*` | Mirror/CDN for the above images |
