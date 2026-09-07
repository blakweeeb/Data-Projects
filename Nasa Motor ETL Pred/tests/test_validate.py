"""Pruebas unitarias de validación / calidad de datos."""

import pandas as pd

from src.validate import validate


def test_validate_ok():
    df = pd.DataFrame({"id": [1, 1], "cycle": [1, 2], "rul": [1, 0]})
    assert validate(df) == []


def test_validate_nulos():
    df = pd.DataFrame({"id": [1], "cycle": [1], "rul": [None]})
    errors = validate(df)
    assert any("nulos" in e for e in errors)


def test_validate_rul_negativo():
    df = pd.DataFrame({"id": [1], "cycle": [5], "rul": [-1]})
    errors = validate(df)
    assert any("RUL negativos" in e for e in errors)


def test_validate_vacio():
    df = pd.DataFrame(columns=["id", "cycle", "rul"])
    errors = validate(df)
    assert any("vacío" in e for e in errors)
