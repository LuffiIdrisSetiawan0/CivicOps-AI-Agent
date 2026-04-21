import pytest

from app.data_seed import bootstrap
from app.db import SessionLocal
from app.services.sql_tool import execute_safe_sql, validate_sql


def test_validate_sql_allows_select() -> None:
    assert validate_sql("SELECT * FROM regions") == "SELECT * FROM regions"


def test_validate_sql_blocks_destructive_statement() -> None:
    with pytest.raises(ValueError):
        validate_sql("DROP TABLE regions")


def test_execute_safe_sql_returns_rows() -> None:
    with SessionLocal() as db:
        bootstrap(db)

    result = execute_safe_sql("SELECT name, province FROM regions ORDER BY name")

    assert result.columns == ["name", "province"]
    assert result.rows
    assert "Kalimantan Tengah" in {row["province"] for row in result.rows}

