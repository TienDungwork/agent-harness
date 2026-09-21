from agent.tools.postgres.validator import validate_sql


def test_select_pass():
    assert validate_sql("SELECT 1").ok


def test_with_pass():
    assert validate_sql("WITH x AS (SELECT 1 AS a) SELECT a FROM x").ok


def test_trailing_semicolon_ok():
    assert validate_sql("SELECT 1;").ok


def test_insert_reject():
    assert not validate_sql("INSERT INTO t VALUES (1)").ok


def test_update_reject():
    assert not validate_sql("UPDATE t SET a = 1").ok


def test_delete_reject():
    assert not validate_sql("DELETE FROM t").ok


def test_drop_reject():
    assert not validate_sql("DROP TABLE t").ok


def test_alter_reject():
    assert not validate_sql("ALTER TABLE t ADD COLUMN a int").ok


def test_truncate_reject():
    assert not validate_sql("TRUNCATE TABLE t").ok


def test_create_reject():
    assert not validate_sql("CREATE TABLE t (a int)").ok


def test_multi_statement_reject():
    r = validate_sql("SELECT 1; DROP TABLE t")
    assert not r.ok
    assert "multi-statement" in r.reason.lower() or "multi" in r.reason.lower()


def test_select_into_reject():
    assert not validate_sql("SELECT * INTO new_t FROM t").ok


def test_empty_reject():
    assert not validate_sql("").ok


def test_string_containing_insert_still_select():
    assert validate_sql("SELECT 'INSERT' AS x").ok


_MIXED = [
    {
        "table": "camera",
        "database": "vms_db",
        "schema": {"columns": [{"column_name": "code"}, {"column_name": "name"}]},
    },
    {
        "table": "plate_event",
        "database": "its",
        "schema": {"columns": [{"column_name": "camera_code"}, {"column_name": "camera_name"}]},
    },
]


def test_reject_camera_code_on_camera_table():
    r = validate_sql("SELECT COUNT(DISTINCT camera_code) FROM camera", _MIXED)
    assert not r.ok
    assert "camera_code" in r.reason


def test_allow_camera_code_on_plate_event():
    r = validate_sql("SELECT COUNT(DISTINCT camera_code) FROM plate_event", _MIXED)
    assert r.ok


def test_reject_table_not_in_schema():
    only_plate = [_MIXED[1]]
    r = validate_sql("SELECT COUNT(DISTINCT camera_code) FROM camera", only_plate)
    assert not r.ok
    assert "camera" in r.reason.lower()


def test_with_still_ok_with_schema():
    r = validate_sql(
        "WITH x AS (SELECT camera_code FROM plate_event) SELECT camera_code FROM x",
        _MIXED,
    )
    assert r.ok
