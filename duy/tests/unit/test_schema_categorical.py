from agent.services.schema_service import is_categorical_column


def test_status_varchar_is_categorical():
    assert is_categorical_column("status", "character varying(32)")


def test_name_is_not_categorical():
    assert not is_categorical_column("name", "character varying(255)")


def test_password_is_not_categorical():
    assert not is_categorical_column("status", "integer")
    assert not is_categorical_column("password", "text")
