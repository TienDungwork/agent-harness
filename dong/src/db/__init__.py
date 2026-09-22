"""Database layer cho dong v5 (catalog, builder, validator, executor)."""

from src.db.catalog import (
    build_schema_excerpt,
    describe_table,
    get_allowed_columns,
    get_allowed_tables,
    get_catalog,
    get_database_for_table,
)
from src.db.connection import get_connection
from src.db.executor import execute_sql
from src.db.query_builder import build_sql
from src.db.validator import ValidationResult, validate_sql

__all__ = [
    "get_catalog",
    "get_allowed_tables",
    "get_allowed_columns",
    "get_database_for_table",
    "describe_table",
    "build_schema_excerpt",
    "build_sql",
    "ValidationResult",
    "validate_sql",
    "execute_sql",
    "get_connection",
]
