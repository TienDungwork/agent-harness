from agent.services.query_service import execute_query
from agent.tools.postgres.validator import validate_sql


def query(dbname: str, sql: str) -> dict:
    check = validate_sql(sql)
    if not check.ok:
        raise ValueError(f"SQL bị từ chối: {check.reason}")
    return execute_query(dbname, sql)
