# Beszel (host monitoring)

Primary run path is **Agent Canvas compose**. From `agent-canvas/`:

```bash
docker compose up -d
```

UI: http://127.0.0.1:18090 — `admin@creanova.local` / `admin123`

S.M.A.R.T.: Canvas agent uses `henrygd/beszel-agent-nvidia` with `/dev/nvme0` + `SYS_RAWIO`/`SYS_ADMIN` (Beszel docs). Host binary agents (Infra deploy) install `smartmontools` and set caps when sudo is available. Re-deploy agents after pulling this change, or on each host:

```bash
sudo apt install -y smartmontools
sudo setcap cap_sys_rawio,cap_sys_admin+ep "$(command -v smartctl)"
sudo usermod -aG disk "$USER"
# NVMe often 600 root:root — see https://beszel.dev/guide/smart-data
```

This `deploy/beszel/` file is a hub-only leftover. Prefer the Canvas stack so the host agent is bootstrapped automatically.
