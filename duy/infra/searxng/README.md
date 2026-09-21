# SearXNG (tự host)

Meta-search miễn phí cho intent `web_search` của DUY.

## Lần đầu

```bash
cd infra/searxng
cp .env.example .env
cp core-config/settings.yml.example core-config/settings.yml
# Sửa secret_key trong settings.yml:
openssl rand -hex 32
docker compose up -d
```

Kiểm tra:

```bash
curl -s 'http://127.0.0.1:8889/search?q=ALPR&format=json' | head -c 300
```

## Vận hành

```bash
docker compose logs -f core
docker compose down
docker compose pull && docker compose up -d
```

Chỉ lắng nghe localhost (`127.0.0.1:8889`) — agent gọi nội bộ, không cần mở ra internet.
