from src.config import settings
import urllib.request
import urllib.parse
import json

import re

def clickhouse_query(sql: str, params: dict) -> list:
    clean_sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    clean_sql = re.sub(r'/\*.*?\*/', '', clean_sql, flags=re.DOTALL)
    if not clean_sql.strip().upper().startswith("SELECT"):
        raise RuntimeError("Từ chối truy vấn: Chỉ cho phép truy vấn SELECT. Không hỗ trợ INSERT/UPDATE/DELETE/DROP/ALTER.")

    url = f"http://{settings.ch_host}:{settings.ch_port}/?database={settings.ch_database}&default_format=JSON"
    # Format sql with params
    # Note: Clickhouse over HTTP expects params to be passed as query parameters with param_ prefix
    # But a simple way is just replacing them, but let's pass them correctly.
    query_params = {}
    for k, v in params.items():
        query_params[f"param_{k}"] = v
    query_string = urllib.parse.urlencode(query_params)
    if query_string:
        url += f"&{query_string}"
    
    req = urllib.request.Request(url, data=sql.encode('utf-8'), method="POST")
    req.add_header("X-ClickHouse-User", settings.ch_user)
    if settings.ch_password:
        req.add_header("X-ClickHouse-Key", settings.ch_password)
        
    try:
        with urllib.request.urlopen(req, timeout=settings.db_query_timeout_s) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get("data", [])
    except Exception as e:
        raise RuntimeError(f"Lỗi truy vấn ClickHouse: {e}")

