"""Pruebas de la capa warehouse (sin necesidad de levantar Postgres)."""

from src.warehouse import FACT_COLS, DDL, check_cuadratura


def test_fact_cols_tienen_31_columnas():
    assert len(FACT_COLS) == 31
    assert FACT_COLS[0] == "motor_id"
    assert "rul_predicho" in FACT_COLS
    assert "error" in FACT_COLS


def test_ddl_crea_tablas_estrella():
    assert "CREATE TABLE IF NOT EXISTS dim_motor" in DDL
    assert "CREATE TABLE IF NOT EXISTS fact_lecturas" in DDL
    assert "VARCHAR(8)" in DDL
    assert "FLOAT" in DDL


def test_check_cuadratura_ok():
    assert check_cuadratura(100, 100) is True


def test_check_cuadratura_falla():
    import pytest
    with pytest.raises(AssertionError, match="Cuadratura fallida"):
        check_cuadratura(100, 99)
