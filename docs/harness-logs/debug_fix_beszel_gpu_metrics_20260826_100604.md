# Execution Log: Beszel GPU VRAM / utilization metrics not working

- **Category**: debug_fix
- **Task**: Investigate why GPU VRAM and GPU % metrics do not work on Beszel agents
- **Started**: 2026-08-26 10:06:04
- **Pipeline**: 4a/4b (04-bugfinder first)

## Skills
<!-- sections appended after each skill -->

## 04-bugfinder
- **Status**: completed
- **Time**: 2026-08-26 ~10:15
- **Findings**:
  - Primary (container GPU % + VRAM columns): agent lacks `pid: host`. `nvidia-smi` returns host PIDs; without host PID namespace `/proc/<pid>/cgroup` is missing and `containerIdFromPid` never maps. Also `nvidia-smi pmon` returns all `-` without `pid: host` (SM% empty). DB: 218 containers, all `gpu=0` `gpu_mem=0`.
  - Secondary (host GPU charts on canvas agent 250): `GPU_COLLECTOR=nvml` but `system_stats` has `NO_G` for local system; remotes using host binary + nvidia-smi have full GPU data. No NVML warn in agent logs; nvidia-smi collector does start a child when forced.
- **Evidence**: docker inspect PidMode empty; pmon with/without pid host; sqlite aggregates; compose `agent-canvas/docker-compose.yml` GPU_COLLECTOR=nvml without pid: host
- **Next**: 05-fix — add `pid: host`; prefer `GPU_COLLECTOR=nvidia-smi` (or `nvidia-smi,nvml`) for reliable host metrics on Docker agent
- **Open questions**: exact NVML init/collect failure mode inside distroless image (no Warn logged) — workaround via nvidia-smi is sufficient

## 05-fix
- **Status**: completed
- **Time**: 2026-08-26 ~11:50
- **Changes**:
  - `agent-canvas/docker-compose.yml`: `pid: host`, `GPU_COLLECTOR=nvidia-smi`, image `creanova/beszel-agent:gpu-containers`
  - `services/beszel/agent/gpu.go`: one-shot `nvidia-smi` poll (not piped `-l`) for host GPU in Docker
  - Custom agent/hub images rebuilt; bootstrap recreate
- **Verification (system 191 = canvas host 192.168.1.191)**:
  - `system_stats.g`: GeForce RTX 3090 mu/u/p present
  - containers: 12 with `gpu_mem>0` (max ~1535 MB), some non-zero `gpu` %
  - `systems.info.g` ≈ 34
- **Note**: system **250** (`192.168.1.250`) is a separate agent host; still NO_G until that agent gets the same fix.
