"""Módulo de validación / controles de calidad de datos."""

import pandas as pd


def validate(df: pd.DataFrame) -> list[str]:
    """Ejecuta controles de calidad. Devuelve lista de errores (vacía = OK)."""
    errors: list[str] = []

    if df.isnull().any().any():
        cols = df.columns[df.isnull().any()].tolist()
        errors.append(f"Valores nulos en: {cols}")

    if (df["rul"] < 0).any():
        errors.append("Se encontraron valores RUL negativos")

    if df["id"].nunique() == 0:
        errors.append("No hay motores (id) en los datos")

    if not df["cycle"].dtype.kind in "if":
        errors.append("La columna 'cycle' no es numérica")

    if df.empty:
        errors.append("El DataFrame está vacío")

    return errors


def assert_quality(df: pd.DataFrame) -> None:
    """Lanza AssertionError si la validación falla."""
    errors = validate(df)
    assert not errors, f"Fallos de calidad: {errors}"
    print("[validate] Controles de calidad OK")


if __name__ == "__main__":
    import transform
    from config import CURATED_DIR

    for pq in CURATED_DIR.glob("*.parquet"):
        df = pd.read_parquet(pq)
        assert_quality(df)
