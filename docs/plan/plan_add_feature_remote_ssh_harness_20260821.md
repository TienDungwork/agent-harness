# Kế hoạch: Remote SSH harness

> Goal: Chat resolve host + chạy lệnh remote qua gateway.

**Architecture:** SQL resolve nhanh + `POST .../run` + token agent + cập nhật LOCAL_HARNESS + MCP tools.

## Tasks

1. `infra/resolve.py` + `infra/destructive.py` + unit tests
2. Config `infra_agent_token` + auth header trong `get_auth_user`
3. Endpoints resolve + run + index hostname
4. MCP tools `infra_resolve_server`, `infra_run`
5. Cập nhật `LOCAL_HARNESS` + compose/dev env `INFRA_AGENT_TOKEN`
6. CHANGELOG + commit `beta v0.5.39`
