# Changelog

All notable changes to this workspace are listed here.

## [beta v0.5.46] - 2026-08-22

### Fixed

- Beszel pin click no-op: nginx `/creanova-api` now proxies to `local-gateway:18110` (was host:18110, unpublished)
- Star alignment + filled amber when pinned; optimistic toggle + toast on failure

## [beta v0.5.45] - 2026-08-22

### Changed

- Beszel container pin icon: 5-point star (filled amber when pinned, hover-only when not)

## [beta v0.5.44] - 2026-08-22

### Changed

- Beszel container pin UX: slim pushpin only on row hover; pinned stays subtly visible; removed always-on pin column

## [beta v0.5.43] - 2026-08-21

### Fixed

- Beszel Containers hang: removed MutationObserver-fighting DOM pin injection from branding.js

### Changed

- Native Containers pin column (lucide Pin icon, ghost icon button); pinned rows float to top; account pins still in gateway DB via `/creanova-api` nginx proxy

## [beta v0.5.43] - 2026-08-21

### Fixed

- local-gateway settings blob no longer stores PATCH diffs (base_url/API key looked wiped after LLM profile updates)
- Invalidate settings blob on profile activate so UI picks up the applied model
- Preserve custom LLM `base_url` when changing model in Basic tab; auto-append `/v1` for OpenAI-compatible host roots

## [beta v0.5.42] - 2026-08-21

### Fixed

- local-gateway forwards `POST /api/auth/workspace-session` to agent-server (was 404 `Not found` after adding/using an LLM profile)

## [beta v0.5.41] - 2026-08-21

### Added

- Beszel ↔ Keycloak OIDC (client `beszel`); bootstrap configures PocketBase OAuth via `_superusers`
- Per-user pinned containers: Beszel UI Pin buttons → `infra_pinned_containers` on local-gateway
- Agent search: `GET /api/infra/pinned-containers/search` + MCP `infra_search_pinned_containers`
- Pin auth via Beszel JWT (`X-Beszel-Token`) mapped to Creanova user by email

## [beta v0.5.40] - 2026-08-21

### Added

- Beszel alert SMTP via Mailpit by default (`mailpit` service, UI `:18025`); `beszel-bootstrap` enables PocketBase SMTP + unhides admin controls so alert emails work without manual `/_/#/settings/mail`

## [beta v0.5.39] - 2026-08-21

### Added

- Remote SSH harness: `GET /api/infra/servers/resolve` (exact-first host lookup) and `POST /api/infra/servers/{id}/run` (full shell via gateway credentials)
- Destructive remote commands require `confirm_destructive=true` after user confirmation
- Agent auth via `X-Creanova-Infra-Token` / `INFRA_AGENT_TOKEN` (persisted with canvas state)
- LOCAL_HARNESS rules for resolve → sticky target → run; infra-mcp tools `infra_resolve_server` / `infra_run`

## [beta v0.5.38] - 2026-08-21

### Fixed

- LLM profile switch/save: reject Cursor product models (auto/api.cursor.com), normalize bare models to openai/… for LiteLLM custom base URLs

## [beta v0.5.37] - 2026-08-21

### Changed

- Beszel S.M.A.R.T. (approach A): Canvas agent uses `beszel-agent-nvidia` with `/dev/nvme0` + `SYS_RAWIO`/`SYS_ADMIN`; Infra deploy installs `smartmontools`, setcap/udev for binary agents, and `:alpine` + device caps for Docker agents

## [beta v0.5.36] - 2026-08-20

### Fixed

- Map UI agent_kind Creanova → wire openhands so saving agent profiles no longer 422s against agent-server

## [beta v0.5.35] - 2026-08-20

### Fixed

- Host picker `+` opens a floating portal menu; picking a host opens/focuses an SSH session tab instead of resetting to Vaults and overlaying the terminal
- local-gateway: stop caching GET /api/profiles in per-user blobs so Add LLM Profile updates the Available Profiles list

## [beta v0.5.34] - 2026-08-20

### Fixed

- Active SSH session tabs keep a fixed 42px height (only widen horizontally); no longer grow taller and shift the tab bar

## [beta v0.5.33] - 2026-08-20

### Changed

- Host tab-bar `+` opens a Termius-style Recent connections picker (search + pick existing host to SSH); New host stays inside the popover for admins; Ctrl+K opens the picker

## [beta v0.5.32] - 2026-08-20

### Changed

- Host vault quick-add `+` sits on the Vaults/SSH tab bar (same row as session chips)

## [beta v0.5.31] - 2026-08-20

### Changed

- Host vault: quick-add `+` beside the Hosts heading (replaces the New host chip); Terminal chip stays in the toolbar

## [beta v0.5.30] - 2026-08-20

### Changed

- SSH host tabs are wider by default; the active tab stretches further for clearer selection

## [beta v0.5.29] - 2026-08-20

### Changed

- SSH tab bar: drop SFTP; close (X) always after the tab title; remove session status/Font/Reconnect toolbar

## [beta v0.5.28] - 2026-08-20

### Changed

- Creanova Beszel wordmark gap to Search tightened to `0.15rem`

## [beta v0.5.27] - 2026-08-20

### Changed

- Containers table: GPU sits next to VRAM (renamed from GPU Mem)

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
