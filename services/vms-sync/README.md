# vms-sync — copy VMS AI events from Postgres into ClickHouse.

See `deploy/clickhouse/README.md` for boot, MCP, and verify.

```bash
cd services/vms-sync
uv sync --extra test
uv run pytest -q
```
