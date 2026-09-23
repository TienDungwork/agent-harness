"""Database layer cho dong v5 (catalog, builder, validator, executor)."""

from src.db.catalog import (
    build_schema_excerpt,
    describe_table,
    get_allowed_columns,
    get_allowed_tables,
    get_catalog,
    get_database_for_table,
    select_relevant_tables,
)
from src.db.connection import get_connection
from src.db.executor import execute_sql
from src.db.validator import ValidationResult, validate_sql

__all__ = [
    "get_catalog",
    "get_allowed_tables",
    "get_allowed_columns",
    "get_database_for_table",
    "describe_table",
    "build_schema_excerpt",
    "select_relevant_tables",
    "ValidationResult",
    "validate_sql",
    "execute_sql",
    "get_connection",
]
