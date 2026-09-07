"""Orquestador local (sin Airflow) para ejecutar el pipeline completo."""

import pandas as pd

from src.config import CURATED_DIR, PROCESSED_DIR, RAW_DIR
from src.ingest import ingest
from src.transform import transform_pandas
from src.validate import assert_quality


def run_pipeline() -> None:
    print("=== PIPELINE ETL MANTENIMIENTO PREDICTIVO ===")
    for txt in sorted(RAW_DIR.glob("*.txt")):
        try:
            ingest(txt)
        except ValueError as e:
            print(f"[omitido] {e}")
            continue
        name = txt.stem + ".parquet"
        path_proc = PROCESSED_DIR / name
        path_curated = CURATED_DIR / name
        transform_pandas(path_proc, path_curated)
        df_curated = pd.read_parquet(path_curated)
        assert_quality(df_curated)
    print("=== PIPELINE COMPLETADO ===")


if __name__ == "__main__":
    run_pipeline()
