---
name: vms-analytics
description: Answer VMS history questions (plates, faces, cameras, fire, anomaly) via gateway tools. Never write SQL. Use when the user asks about biển số, smartface, virtual fence, anomaly, cháy khói, or camera rankings.
triggers:
- clickhouse
- vms
- biển số
- smartface
- virtual fence
- anomaly
- báo cáo
- cháy
- leo trèo
---

# VMS analytics (tools only)

The user asks in natural language. **Do not write ClickHouse or Postgres SQL.** Do not use `mcp-clickhouse`, `clickhouse-client`, or POST SQL to port 8123. Pick one gateway tool and pass arguments.

Header: `X-Creanova-Infra-Token: $INFRA_AGENT_TOKEN`. Base: `${INFRA_GATEWAY_URL:-http://local-gateway:18110}`.

## Tools

Counts (how many alerts recently):

```bash
curl -sS -H "X-Creanova-Infra-Token: $INFRA_AGENT_TOKEN" \
  "${INFRA_GATEWAY_URL:-http://local-gateway:18110}/api/infra/analytics/summary?days=7&module=ANOMALY"
```

Top cameras (which camera had the most climbing / fire / plates):

```bash
curl -sS -H "X-Creanova-Infra-Token: $INFRA_AGENT_TOKEN" \
  "${INFRA_GATEWAY_URL:-http://local-gateway:18110}/api/infra/analytics/top-cameras?days=30&module=ANOMALY&event_type=INTRUSION_DETECTION"
```

License plate:

```bash
curl -sS -H "X-Creanova-Infra-Token: $INFRA_AGENT_TOKEN" \
  "${INFRA_GATEWAY_URL:-http://local-gateway:18110}/api/infra/analytics/search-plate?q=PLATE"
```

Person name (face / zone):

```bash
curl -sS -H "X-Creanova-Infra-Token: $INFRA_AGENT_TOKEN" \
  "${INFRA_GATEWAY_URL:-http://local-gateway:18110}/api/infra/analytics/search-person?q=NAME"
```

Daily trend:

```bash
curl -sS -H "X-Creanova-Infra-Token: $INFRA_AGENT_TOKEN" \
  "${INFRA_GATEWAY_URL:-http://local-gateway:18110}/api/infra/analytics/daily?days=30"
```

MCP names (same tools): `vms_summary`, `vms_top_cameras`, `vms_search_plate`, `vms_search_person`, `vms_daily`.

`module`: `FACE` | `PLATE` | `ZONE` | `ANOMALY` | `FIRE`

Useful `event_type`: `INTRUSION_DETECTION`, `FIGHT_DETECTION`, `WATER_LEVEL_DETECTION`, `HIGH`, `IN`, `OUT`

Live “who is in a zone now” is Postgres `zone_presence`, not these tools. Warehouse lag is 1–5 minutes.
