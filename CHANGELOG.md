# Changelog

All notable changes to this workspace are listed here.

## [beta v0.5.26] - 2026-08-20

### Changed

- Creanova Beszel wordmark: slightly larger (`1.5rem`) and closer to Search (`0.25rem` gap)

## [beta v0.5.25] - 2026-08-20

### Changed

- SSH workspace tab bar: Termius-style Vaults/SFTP pills, host session chips with status dot, green active tab; roomier status toolbar

## [beta v0.5.24] - 2026-08-20

### Removed

- Beszel command-palette “Documentation” (beszel.dev) entry under Creanova branding

## [beta v0.5.23] - 2026-08-20

### Removed

- Host vault Monitor tab (Beszel at `:18090` owns monitoring)

## [beta v0.5.22] - 2026-08-20

### Removed

- Host vault toolbar Serial and Details chip buttons (open details via pencil / New host)

## [beta v0.5.21] - 2026-08-20

### Fixed

- Creanova Beszel wordmark no longer horizontally stretched (removed SVG `textLength`)

## [beta v0.5.20] - 2026-08-20

### Changed

- Host vault chrome (left nav, Hosts heading, toolbar chips, card titles) matches LLM settings text size/brightness (`text-sm`/`text-base` medium white)

## [beta v0.5.19] - 2026-08-20

### Fixed

- Beszel Creanova branding: larger tighter wordmark, no Beszel flash on refresh, Home icon mounts as soon as the navbar appears

## [beta v0.5.18] - 2026-08-20

### Changed

- Host Details headings (Address / General / Credentials / panel title) use brighter white semibold text, closer to Termius

## [beta v0.5.17] - 2026-08-20

### Changed

- Clicking empty space in the Host vault grid closes the Host Details panel when it is open

## [beta v0.5.16] - 2026-08-20

### Changed

- Host vault cards: single click selects only; hover pencil opens Host Details (panel no longer auto-opens on select)

## [beta v0.5.15] - 2026-08-20

### Changed

- Beszel public UI (`:18090`) rewrites `<title>` to Creanova at the nginx layer (faster first paint)

## [beta v0.5.15] - 2026-08-20

### Added

- Beszel container table: GPU % and GPU Mem columns (nvidia-smi process → Docker cgroup), matching host GPU collector style
- Custom hub image `creanova/beszel:gpu-containers` (built from `services/beszel`) so UI + DB fields ship together

## [beta v0.5.14] - 2026-08-20

### Changed

- Beszel “All Systems” control is a Home icon in the top-right icon row (same Lucide style as containers / settings), not text

## [beta v0.5.13] - 2026-08-20

### Changed

- Beszel hub UI branding: header logo + browser tab title show **Creanova** (SVG wordmark via nginx `:18090` and Host → Monitor proxy)

## [beta v0.5.12] - 2026-08-20

### Changed

- Host vault cards polished: always-on border, richer circular icon, taller card, larger title, smaller IP · user line, compact `ssh` chip

## [beta v0.5.11] - 2026-08-20

### Changed

- Host vault cards show IP · username on the subtitle instead of `ssh`/tags
- Canvas Docker overlay rebuild skips `npm ci` when `node_modules` already exists; prefer host `npm run build:app` for UI tweaks

## [beta v0.5.11] - 2026-08-20

### Added

- Beszel “All Systems” home control (next to logo on `:18090`, plus Host → Monitor toolbar) to leave a system detail page

## [beta v0.5.10] - 2026-08-20

### Fixed

- Beszel GPU metrics on NVIDIA hosts: deploy host binary (uses `nvidia-smi`) instead of the Docker agent image, which cannot see the GPU
- Redeploy clears Beszel agent fingerprint so Docker ↔ binary switches do not get stuck on fingerprint mismatch

## [beta v0.5.9] - 2026-08-20

### Changed

- Host vault list uses a Termius-style wrapping card grid (circular icon, title, `ssh`/tags) instead of one full-width row per host

## [beta v0.5.8] - 2026-08-19


### Fixed

- Host details ⋯ menu opens Connect and Remove on the same page instead of a new tab

### Changed

- Host details panel auto-saves after edits; footer Save/Delete buttons removed (remove is under the ⋯ menu)

## [beta v0.5.7] - 2026-08-19

### Fixed

- Beszel agents now use a unique listen port per host (`45000` + last IP octet) and report to the hub at `BESZEL_HUB_PUBLIC_URL` (`http://192.168.1.191:18090`)


### Changed

- Host cards keep original height/style; width is ~1/3 so three hosts fit on one row

## [beta v0.5.5] - 2026-08-19

### Fixed

- Adding or renaming an SSH host now updates Beszel All Systems immediately (label = host name)
- Auto-deploy of beszel-agent on save no longer fails silently; SSH install waits up to 3 minutes for image pull


### Changed

- Host vault cards: compact Termius-style rectangles (icon + name + `ssh, user`) in a wrapping row

## [beta v0.5.3] - 2026-08-19

### Removed

- Settings / Customize sidebar line “These settings are synced from … backend (…)”

## [beta v0.4.0] - 2026-08-19

### Added

- Beszel hub + agent in Agent Canvas compose (`docker compose up` starts monitoring at `:18090`)

## [beta v0.3.0] - 2026-08-18

### Added

- Local Creanova agent prompt overlay: `SOUL.md` identity plus `<LOCAL_HARNESS>` suffix on every Canvas conversation (SSH/host, runtime image, no Claude Code prompt)

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
