# Agent Canvas + Beszel — setup máy mới

Đọc file này khi **đổi / dựng lại server**. Làm theo thứ tự; không skip bước build image Beszel.

Repo giả định: clone OpenHands, thư mục làm việc chính là `agent-canvas/`.

```text
OpenHands/
├── agent-canvas/          ← bạn đứng ở đây hầu hết lệnh
│   ├── setup.md           ← file này
│   ├── docker-compose.yml
│   ├── docker/build-beszel-gpu.sh
│   └── .env.sample
└── services/
    ├── beszel/            ← source hub/agent (build local)
    └── local-gateway/
```

---

## 0. Checklist nhanh (máy đã có Docker)

```bash
cd /path/to/OpenHands/agent-canvas
cp -n .env.sample .env          # lần đầu
bash docker/build-beszel-gpu.sh # BẮT BUỘC — image không có trên Docker Hub
docker compose --profile overlay-build run --rm canvas-ui-build   # lần đầu / khi cần UI overlay
docker compose up -d
```

URLs mặc định:

| Service | URL | Login |
|---------|-----|--------|
| Canvas | http://\<IP\>:18010/agents/ | `admin` / `admin123` (local auth) |
| Path gateway | http://\<IP\>:18000/ | `/agents` `/admin` `/monitoring` — see `deploy/gateway/` |
| Beszel | http://\<IP\>:18090/ | `admin@creanova.local` / `admin123` |
| Mailpit (alert mail) | http://\<IP\>:18025/ | — |

---

## 1. Prerequisites (máy mới)

- Linux + Docker Engine + Compose v2
- User trong group `docker` (`docker ps` không cần sudo)
- **NVIDIA** (cho Beszel agent GPU):
  - Driver + `nvidia-smi` chạy được
  - [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) — `docker info` có runtime `nvidia`
- Disk NVMe (optional SMART): compose map `/dev/nvme0`. Không có thì sửa `beszel-agent.devices` trong `docker-compose.yml` (comment hoặc đổi device) trước khi `up`
- Network Docker: bridge **không** được overlap LAN/VPN. Compose này dùng subnet cố định `10.240.120.0/24`. Khuyến nghị daemon pool `10.240.0.0/16` (xem `services/beszel/AGENTS.md`)

Kiểm tra nhanh:

```bash
docker info | grep -i nvidia
nvidia-smi -L
ls /dev/nvme0 || echo "no nvme0 — edit compose devices before up"
```

---

## 2. Env

```bash
cd /path/to/OpenHands/agent-canvas
cp -n .env.sample .env
```

Chỉnh tối thiểu khi đổi máy / IP LAN:

| Biến | Ý nghĩa | Gợi ý |
|------|---------|--------|
| `BESZEL_APP_URL` | URL browser mở Beszel | `http://192.168.x.x:18090` |
| `BESZEL_HUB_PUBLIC_URL` | Gateway/UI link ra hub | cùng host:port public |
| `BESZEL_HUB_URL` | Agent (host network) gọi hub | thường `http://127.0.0.1:18090` |
| `BESZEL_PORT` | Port host Beszel UI | `18090` |
| `CANVAS_HOST_PORT` | Port Canvas | `18010` |
| `MAILPIT_UI_PORT` | Port Mailpit | `18025` |
| `CORS_ORIGINS` | Thêm origin Canvas/Beszel theo IP máy mới | xem default trong compose |
| `KEYCLOAK_PUBLIC_URL` | OIDC (nếu bật) | tắt OIDC: `BESZEL_OIDC_ENABLED=false` |
| `PROJECTS_PATH` | Mount `/projects` vào canvas | mặc định `$HOME/projects` |

Login Beszel mặc định: `BESZEL_USER_EMAIL` / `BESZEL_USER_PASSWORD` (`admin@creanova.local` / `admin123`).

---

## 3. Build image Beszel (bắt buộc mỗi máy mới)

`creanova/beszel:gpu-containers` và `creanova/beszel-agent:gpu-containers` **chỉ local**. Compose có `pull_policy: never` — không login Docker Hub cũng không pull được.

**Đứng trong `agent-canvas/`** (không dùng path `agent-canvas/docker/...` khi đã `cd` vào trong):

```bash
cd /path/to/OpenHands/agent-canvas
bash docker/build-beszel-gpu.sh
```

Script sẽ:

1. Compile agent + hub từ `services/beszel`
2. Build UI web hub
3. Tag 2 image: `creanova/beszel:gpu-containers`, `creanova/beszel-agent:gpu-containers`

Lần đầu chậm (kéo `golang`, `node`, `henrygd/beszel-agent-nvidia`). Các lần sau nhanh hơn nhờ cache.

Xác nhận:

```bash
docker images 'creanova/beszel*'
# phải thấy cả 2 tag gpu-containers
```

### Lỗi thường gặp

| Triệu chứng | Nguyên nhân | Cách xử lý |
|-------------|-------------|------------|
| `pull access denied for creanova/beszel-agent` | Chưa build local / đứng sai máy | `bash docker/build-beszel-gpu.sh` rồi `compose up` lại |
| `No such file or directory` khi `bash agent-canvas/docker/...` | Đã `cd agent-canvas` nhưng path còn prefix | Dùng `bash docker/build-beszel-gpu.sh` |
| Build agent `COPY build/beszel-agent` not found | `.dockerignore` loại `build/` | Dùng script trên (đã stage binary); đừng `docker build -f Dockerfile.agent-gpu-containers .` trực tiếp trừ khi biết cách bypass |

---

## 4. Overlay UI Canvas (lần đầu)

Image runtime không chứa UI Creanova/Hosts mới nhất — cần build overlay vào `./build`:

```bash
cd /path/to/OpenHands/agent-canvas
docker compose --profile overlay-build run --rm canvas-ui-build
```

Nếu `build/` / `public/locales` bị root sở hữu sau Docker build:

```bash
sudo chown -R "$USER:$USER" build public/locales
```

Iterate UI nhanh (không rebuild Docker image):

```bash
VITE_BASE_PATH=/agents VITE_LOCAL_AUTH_ENABLED=true npm run build:app
docker compose restart agent-canvas
# hard-refresh browser → http://localhost:18010/agents/ or :18000/agents/
```

---

## 5. Start stack

### Full stack

```bash
cd /path/to/OpenHands/agent-canvas
docker compose up -d
```

### Chỉ Beszel (+ deps: mailpit, gateway nếu UI cần)

```bash
docker compose up -d mailpit local-gateway agent-canvas \
  beszel beszel-ui beszel-bootstrap beszel-agent
```

Thứ tự nội bộ: `beszel` healthy → `beszel-bootstrap` (SMTP/OIDC + sync InfraServer) → `beszel-agent`.

Kiểm tra:

```bash
docker compose ps
curl -sf http://127.0.0.1:18090/api/health
docker logs creanova-beszel-bootstrap 2>&1 | tail -20
docker logs creanova-beszel-agent 2>&1 | tail -20
# agent: "WebSocket connected host=127.0.0.1:18090"
```

Systems trên Beszel được sync từ SQLite local-gateway (`infra_servers`). Thêm/sửa host trong Canvas/Hosts rồi chạy lại bootstrap nếu cần:

```bash
docker compose up -d --force-recreate beszel-bootstrap
```

---

## 6. Đổi server — checklist copy/paste

1. Clone / rsync code OpenHands (giữ `agent-canvas` + `services/beszel` + `services/local-gateway`)
2. Cài Docker + nvidia-container-toolkit; xác nhận `nvidia-smi` + runtime `nvidia`
3. `cd agent-canvas && cp -n .env.sample .env` — sửa IP trong `BESZEL_*`, `CORS_ORIGINS`, `KEYCLOAK_*`
4. Sửa `beszel-agent.devices` nếu không có `/dev/nvme0`
5. `bash docker/build-beszel-gpu.sh`
6. `docker compose --profile overlay-build run --rm canvas-ui-build` (lần đầu)
7. `docker compose up -d`
8. Mở `:18010/agents/` (hoặc gateway `:18000/agents/`) và `:18090/` — login như bảng trên
9. (Tuỳ chọn) Path gateway: `docker compose -f ../deploy/gateway/docker-compose.yml up -d` → `:18000/`
10. (Tuỳ chọn) Volume cũ: `docker volume ls | grep agent-canvas` — copy/migrate nếu muốn giữ conversation + Beszel DB

Dừng:

```bash
docker compose down          # giữ volume
docker compose down -v       # XOÁ state (Beszel DB, canvas_state, token agent)
```

---

## 7. Troubleshooting

**Beszel UI 502 / không healthy**

```bash
docker logs creanova-beszel --tail 50
docker compose up -d --force-recreate beszel beszel-ui
```

**Bootstrap exit ≠ 0 → agent không start**

```bash
docker logs creanova-beszel-bootstrap
# Auth / SMTP / OIDC log rồi mới sync systems.
# Sửa xong:
docker compose up -d --force-recreate beszel-bootstrap
docker compose up -d beszel-agent
```

**Agent không GPU / không thấy container GPU %**

- Cần `gpus: all`, `pid: host`, `GPU_COLLECTOR=nvidia-smi`, image `creanova/beszel-agent:gpu-containers` (không dùng upstream thuần)
- Host phải có nvidia-container-toolkit

**OIDC / Keycloak lỗi**

- Tắt tạm: `BESZEL_OIDC_ENABLED=false` trong `.env`, recreate bootstrap
- Hoặc chỉnh `KEYCLOAK_PUBLIC_URL` trỏ đúng Keycloak máy đó (`deploy/local-auth/`)

**Port đã chiếm**

```bash
ss -tlnp | grep -E '18010|18090|18025|45876'
```

Đổi qua `.env` (`CANVAS_HOST_PORT`, `BESZEL_PORT`, `MAILPIT_UI_PORT`). Agent listen `45876` (host network).

**Overlap route LAN/VPN (timeout từ máy khác, server vẫn ping local được)**

```bash
ip route get <IP_client>
# Phải qua gateway LAN, KHÔNG qua br-* Docker
docker network inspect agent-canvas_net --format '{{json .IPAM.Config}}'
```

---

## 8. Thành phần compose (tham chiếu)

| Service | Image / build | Vai trò |
|---------|---------------|---------|
| `agent-canvas` | `ntiendung/agents-harness:…` + overlay `./build` | UI + agent-server ingress |
| `local-gateway` | build `services/local-gateway` | Auth local, Hosts/SSH, Beszel pins |
| `mailpit` | `axllent/mailpit` | SMTP catcher alert |
| `beszel` | `creanova/beszel:gpu-containers` | Hub PocketBase |
| `beszel-ui` | `nginx` | Publish `:18090` + branding JS |
| `beszel-bootstrap` | `alpine` one-shot | Token agent, SMTP, OIDC, sync systems |
| `beszel-agent` | `creanova/beszel-agent:gpu-containers` | Metrics host/GPU/containers |

Volumes quan trọng: `canvas_state`, `beszel_data`, `beszel_shared` (token + pubkey agent), `beszel_agent_data`.
