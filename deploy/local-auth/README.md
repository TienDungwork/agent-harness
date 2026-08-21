# Creanova Local Auth

## Default: **không cần Docker** (`AUTH_BACKEND=local`)

Gateway tự seed user:

| Username | Password | Role |
|----------|----------|------|
| `admin`  | `admin123` | admin |
| `demo`   | `demo123`  | user |

Tạo user mới: login admin → `/admin/users` → Create user (hoặc API `POST /api/admin/users`).

```bash
# agent-canvas/.env
OH_LOCAL_AUTH=1
VITE_LOCAL_AUTH_ENABLED=true
OH_LOCAL_AUTH_BACKEND=local
AUTH_BACKEND=local

cd agent-canvas && npm run dev
# → http://localhost:18010/login
```

## Optional: Keycloak qua Docker (`AUTH_BACKEND=keycloak`)

Chỉ khi bạn muốn IdP riêng. Compose **bắt buộc** subnet `10.240.122.0/24` (Atin191 — tránh overlap LAN/VPN `192.168.x`).

```bash
OH_LOCAL_AUTH_BACKEND=keycloak
AUTH_BACKEND=keycloak
docker compose -f deploy/local-auth/docker-compose.yml up -d
```

- Keycloak admin: http://127.0.0.1:18180 — `admin` / `admin`
- Realm: `creanova`
- Client: `creanova-local` / `creanova-local-secret` (Agents / local-gateway)
- Client: `beszel` / `beszel-local-secret` — OIDC for monitor UI (`:18090/api/oauth2-redirect`)
- Network: `creanova_local_auth_net` → `10.240.122.0/24`

### Docker network rule (tóm tắt)

- Không dùng pool mặc định `192.168.x.0/20` của Docker.
- Mọi Compose trong môi trường Atin191: `subnet: 10.240.<N>.0/24`.
- Root app: `10.240.121.0/24` (`docker-compose.yml`).
- Local auth Keycloak: `10.240.122.0/24` (file này).
- Kiểm tra: `ip route get <client_ip>` không được đi qua `br-*` Docker.

## Gateway env

See `services/local-gateway/.env.example`.
