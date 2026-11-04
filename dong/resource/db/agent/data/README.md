# Agent DB trên disk

PostgreSQL lưu **cluster** tại thư mục con **`pgdata/`** (bind mount từ Docker).

- Trong Explorer có thể thấy folder `pgdata` nhưng **không mở/expand được** trên máy host: quyền `700`, owner là user `postgres` trong container — bình thường.
- Đây **không** phải file `.sql` hay bảng Excel; dữ liệu bảng xem qua **DBeaver** (`localhost:5433`, db `kcn_agent`, user `atin`).

Kiểm tra data có thật trên disk:

```bash
docker exec kcn_agent_postgres ls -la /var/lib/postgresql/data
docker exec kcn_agent_postgres du -sh /var/lib/postgresql/data
docker exec kcn_agent_postgres psql -U atin -d kcn_agent -c '\dt'
```

`pgdata/` nằm trong `.gitignore` — không commit lên git.
