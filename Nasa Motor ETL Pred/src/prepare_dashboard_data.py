"""Prepara dataset unificado para Power BI (une train_FD001..FD004)."""

from pathlib import Path

import pandas as pd

from src.config import CURATED_DIR

OUT = CURATED_DIR / "all_scenarios.parquet"


def prepare(curated_dir: Path = CURATED_DIR, out: Path = OUT) -> pd.DataFrame:
    files = sorted(Path(curated_dir).glob("train_FD00*.parquet"))
    if not files:
        raise FileNotFoundError(f"No se encontraron train_FD00*.parquet en {curated_dir}")
    frames = []
    for f in files:
        df = pd.read_parquet(f)
        df = df.copy()
        df["scenario"] = f.stem.replace("train_", "")  # FD001..FD004
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(out, index=False)
    print(f"[prepare_dashboard] {len(combined)} filas -> {out}")
    print(f"Escenarios: {sorted(combined['scenario'].unique())}")
    return combined


if __name__ == "__main__":
    prepare()
