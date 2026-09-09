# What we use from `ClickHouse/` (plan only)

Upstream checkout: `ClickHouse/` at tag `v26.8.2.7-lts`. Runtime is still the Hub image `clickhouse/clickhouse-server:26.8.2.7` (built from this tag). We do **not** compile `src/` or pull `contrib/`.

Plan: `docs/plan/plan_add_feature_clickhouse_vms_warehouse_20260908.md`

## Use (wired in `deploy/clickhouse/`)

| Plan item | Upstream piece | How we use it |
|-----------|----------------|---------------|
| R8 compose + init | `docker/server/entrypoint.sh` (`/docker-entrypoint-initdb.d`) | Mount `deploy/clickhouse/init/` (image entrypoint) |
| R9 listen in-container | `docker/server/docker_related_config.xml` | Copied to `config.d/docker_related_config.xml` and mounted over the image file |
| R8 / RAM / UTC | `programs/server/config.d/` overlay | `config.d/creanova.xml` |
| R9 ports HTTP/native | `programs/server/config.xml` defaults `8123` / `9000` | Compose publish `127.0.0.1:18123` / `:19000` |
| ulimit | `docker/server/README.md` (`nofile=262144`) | Compose `ulimits.nofile` |
| Image pin | Hub tag `26.8.2.7` = git tag `v26.8.2.7-lts` | Compose digest `sha256:fa394d…` |
| R4 / R7 schema engines | MergeTree family in the **binary** | `init/01_schema.sql` |
| R5 readonly + quota | SQL `SETTINGS PROFILE` / `QUOTA` | `init/02_users.sh` |
| Agent HTTP `{param:Type}` | HTTP interface in the server binary | `services/local-gateway/infra/analytics.py` |

VMS tables, sync worker, and agent tools are **ours** (`deploy/clickhouse/`, `services/vms-sync`, `services/local-gateway`). They are not in the upstream repo.

## Do not use (out of plan)

| Upstream | Why skip |
|----------|----------|
| `src/`, `rust/`, `cmake/`, `contrib/` | Engine compile; Hub image already is this tag |
| `programs/keeper`, cluster XML | Plan is one replica |
| `MaterializedPostgreSQL` / Kafka engines | Plan rejected CDC (no PG restart, no extra bus) |
| `tests/`, `ci/`, `benchmark/`, Play UI HTML | Not warehouse ops |
| Full `programs/server/config.xml` / `users.xml` copy | Image ships them; we only overlay `config.d` + SQL users |

To browse a used file: `ClickHouse/docker/server/entrypoint.sh`, `ClickHouse/docker/server/docker_related_config.xml`.
