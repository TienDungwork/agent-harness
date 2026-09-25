from __future__ import annotations

from psycopg import sql as psql

from agent.services.connection import connect

_HIDDEN_COLUMNS = {
    "password",
    "username",
    "onvif_password",
    "onvif_username",
    "main_stream",
    "sub_stream",
    "sub_stream2",
    "stream_url",
}

_CATEGORICAL_NAMES = {
    "status",
    "state",
    "severity",
    "direction",
    "event_type",
    "entity_type",
    "compliance_status",
    "alert_level",
    "alert_type",
    "quality_status",
    "module_code",
    "violation_type",
    "violation_type_code",
    "device_type",
}

_SAMPLE_LIMIT = 20

_TABLES_SQL = """
SELECT schemaname AS table_schema, tablename AS table_name
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename
"""

_COLUMNS_SQL = """
SELECT
  a.attname AS column_name,
  format_type(a.atttypid, a.atttypmod) AS data_type,
  CASE WHEN a.attnotnull THEN 'NO' ELSE 'YES' END AS is_nullable
FROM pg_attribute a
JOIN pg_class c ON a.attrelid = c.oid
JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE n.nspname = %s
  AND c.relname = %s
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY a.attnum
"""

_PK_SQL = """
SELECT a.attname AS column_name
FROM pg_index i
JOIN pg_class c ON c.oid = i.indrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY (i.indkey)
WHERE i.indisprimary
  AND n.nspname = %s
  AND c.relname = %s
ORDER BY a.attnum
"""

_FK_SQL = """
SELECT
  att.attname AS column_name,
  nf.nspname AS foreign_table_schema,
  cf.relname AS foreign_table_name,
  attf.attname AS foreign_column_name
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_class cf ON cf.oid = con.confrelid
JOIN pg_namespace nf ON nf.oid = cf.relnamespace
JOIN LATERAL unnest(con.conkey, con.confkey) AS u(attnum, fattnum) ON TRUE
JOIN pg_attribute att ON att.attrelid = c.oid AND att.attnum = u.attnum
JOIN pg_attribute attf ON attf.attrelid = cf.oid AND attf.attnum = u.fattnum
WHERE con.contype = 'f'
  AND n.nspname = %s
  AND c.relname = %s
"""


def is_categorical_column(column_name: str, data_type: str) -> bool:
    name = (column_name or "").lower()
    if name in _HIDDEN_COLUMNS or "password" in name:
        return False
    dt = (data_type or "").lower()
    if not any(token in dt for token in ("char", "text", "enum", "name")):
        return False
    return (
        name in _CATEGORICAL_NAMES
        or name.endswith("_status")
        or name.endswith("_state")
        or name.endswith("_type")
        or name.endswith("_code")
        or name.endswith("_level")
    )


def _sample_column_values(conn, schema: str, table: str, column: str) -> list[str]:
    q = psql.SQL(
        "SELECT {col}::text AS v "
        "FROM {sch}.{tbl} "
        "WHERE {col} IS NOT NULL "
        "GROUP BY 1 "
        "ORDER BY COUNT(*) DESC, 1 "
        "LIMIT %s"
    ).format(
        col=psql.Identifier(column),
        sch=psql.Identifier(schema),
        tbl=psql.Identifier(table),
    )
    rows = conn.execute(q, (_SAMPLE_LIMIT,)).fetchall()
    return [r["v"] for r in rows if r.get("v") is not None]


def list_tables(dbname: str) -> list[dict]:
    with connect(dbname) as conn:
        rows = conn.execute(_TABLES_SQL).fetchall()
    return [dict(r) for r in rows]


def describe_table(dbname: str, table: str, schema: str = "public") -> dict:
    with connect(dbname) as conn:
        columns = [
            dict(r)
            for r in conn.execute(_COLUMNS_SQL, (schema, table)).fetchall()
            if str(r["column_name"]).lower() not in _HIDDEN_COLUMNS
            and "password" not in str(r["column_name"]).lower()
        ]
        pks = [r["column_name"] for r in conn.execute(_PK_SQL, (schema, table)).fetchall()]
        fks = [dict(r) for r in conn.execute(_FK_SQL, (schema, table)).fetchall()]
        for col in columns:
            if is_categorical_column(str(col["column_name"]), str(col.get("data_type") or "")):
                try:
                    samples = _sample_column_values(conn, schema, table, str(col["column_name"]))
                except Exception:
                    samples = []
                if samples:
                    col["sample_values"] = samples
    return {
        "database": dbname,
        "schema": schema,
        "table": table,
        "columns": columns,
        "primary_key": pks,
        "foreign_keys": fks,
    }


def get_schema(dbname: str, tables: list[tuple[str, str]] | None = None) -> dict:
    if tables is None:
        tables = [(r["table_schema"], r["table_name"]) for r in list_tables(dbname)]
    return {
        "database": dbname,
        "tables": [describe_table(dbname, table, schema) for schema, table in tables],
    }
