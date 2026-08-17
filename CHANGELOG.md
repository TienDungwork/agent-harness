# Changelog

All notable changes to this workspace are listed here.

## [beta v0.2.0] - 2026-08-17

### Added

- Agent Canvas compose overlay: Hub image stays runtime-only; local UI build, entrypoint, static-server, and local-gateway are bind-mounted on top
- `services/local-gateway` Docker runtime image (deps in `/opt/venv`, source mounted at `/app`)
- `npm run build:overlay` and compose profile `overlay-build` to produce the UI bind-mount

### Changed

- Static server can inject `window.__VITE_LOCAL_AUTH_ENABLED__` at serve time so Hosts / SSH work without baking the Vite flag
- Local-auth client treats an empty build-time env as unset and falls back to the runtime window flag

## [beta v0.1.0] - 2026-08-17

### Added

- Initial Creanova agent-harness snapshot (Agent Canvas, software-agent-sdk, Creanova app server)
- Cursor rules: Karpathy behavioral guidelines; versioning, commit format, and changelog
- `CHANGELOG.md` for dated version history
- Docker Hub image `ntiendung/agents-harness:v1.0.0` (full Agent Canvas 1.5.2 stack)
