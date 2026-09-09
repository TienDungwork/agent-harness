---
name: VMS analytics
type: knowledge
version: 1.2.0
agent: CodeActAgent
triggers:
  - clickhouse
  - vms
  - biển số
  - smartface
  - virtual fence
  - anomaly
  - báo cáo
---

# VMS analytics

The user asks in Vietnamese or English. **Do not write SQL.** Call a gateway tool (or MCP with the same name). Header `X-Creanova-Infra-Token: $INFRA_AGENT_TOKEN`.

| User intent | Tool / path | Args |
|-------------|-------------|------|
| Gần đây có bao nhiêu alert / loại gì | `vms_summary` · `/api/infra/analytics/summary` | `days`, optional `module` |
| Camera nào nhiều leo trèo / cháy / biển số | `vms_top_cameras` · `/top-cameras` | `days`, `module`, `event_type` |
| Biển số X xuất hiện khi nào | `vms_search_plate` · `/search-plate` | `q` = plate |
| Người tên X (face / zone) | `vms_search_person` · `/search-person` | `q` = name |
| Xu hướng theo ngày | `vms_daily` · `/daily` | `days`, optional `module` |

`module`: `FACE` | `PLATE` | `ZONE` | `ANOMALY` | `FIRE` | `FOOTFALL` | `PPE` | `THERMAL` | `HUB`

Useful `event_type`: `INTRUSION_DETECTION`, `FIGHT_DETECTION`, `WATER_LEVEL_DETECTION`, `HIGH`, `IN`, `OUT`

Do not query ClickHouse yourself. Live “ai đang trong zone” is Postgres `zone_presence`, not these tools.
