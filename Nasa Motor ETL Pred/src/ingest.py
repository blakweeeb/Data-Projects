"""Ingesta: lee datos cruros NASA CMAPSS (txt) y guarda como Parquet."""

from pathlib import Path

import pandas as pd

from src.config import COLUMNS, PROCESSED_DIR, RAW_DIR


def ingest(path_raw: str | Path, path_out: str | Path | None = None) -> pd.DataFrame:
    """Lee el archivo crudo (txt separado por espacios) y lo guarda como Parquet.

    Args:
        path_raw: ruta al archivo .txt de NASA CMAPSS.
        path_out: ruta de salida .parquet. Si es None, se genera en PROCESSED_DIR.
    """
    path_raw = Path(path_raw)
    if path_out is None:
        path_out = PROCESSED_DIR / (path_raw.stem + ".parquet")
    Path(path_out).parent.mkdir(parents=True, exist_ok=True)

    with open(path_raw, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                n_fields = len(line.split())
                break
        else:
            raise ValueError(f"{path_raw}: archivo vacío")
    if n_fields != len(COLUMNS):
        raise ValueError(
            f"{path_raw.name}: se esperaban {len(COLUMNS)} columnas "
            f"pero tiene {n_fields}. Verifica que sea el archivo de "
            f"ENTRENAMIENTO (ej. FD001_train.txt). "
            f"RUL_FD001.txt es el ground-truth del test set y no se usa aquí."
        )

    df = pd.read_csv(path_raw, sep=r"\s+", header=None, names=COLUMNS)
    df.to_parquet(path_out, index=False)
    print(f"[ingest] {len(df)} filas -> {path_out}")
    return df


if __name__ == "__main__":
    for txt in RAW_DIR.glob("*.txt"):
        ingest(txt)
