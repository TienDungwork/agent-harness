# Creanova PostgreSQL (port 54288)

## Boot

```bash
cp deploy/data/.env.example deploy/data/.env
# edit POSTGRES_PASSWORD
docker compose -f deploy/data/docker-compose.yml --env-file deploy/data/.env up -d
docker compose -f deploy/data/docker-compose.yml ps
```

- Host: `127.0.0.1:54288`
- DB/user: `creanova` / `creanova` (default)
- Docker network: `creanova_data_net` → `10.240.123.0/24`

Gateway URL:

```text
postgresql+psycopg://creanova:<password>@127.0.0.1:54288/creanova
```

## Backup / restore

```bash
docker exec creanova-postgres pg_dump -U creanova creanova > creanova.dump.sql
docker exec -i creanova-postgres psql -U creanova creanova < creanova.dump.sql
```

## Subnet check (Atin191)

```bash
docker network inspect creanova_data_net --format '{{json .IPAM.Config}}'
ip route get 192.168.82.37   # must go via LAN gateway, not br-*
```
