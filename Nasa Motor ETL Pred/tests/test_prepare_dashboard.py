"""Pruebas para la preparación del dataset de Power BI."""

from pathlib import Path

import pandas as pd

from src.prepare_dashboard_data import prepare
from src.config import CURATED_DIR


def test_prepare_crea_columna_scenario(tmp_path):
    for sc in ["FD001", "FD002"]:
        d = pd.DataFrame({"id": [1], "cycle": [1], "rul": [5], "label": [0]})
        d.to_parquet(tmp_path / f"train_{sc}.parquet", index=False)
    out = tmp_path / "all_scenarios.parquet"
    df = prepare(curated_dir=tmp_path, out=out)
    assert "scenario" in df.columns
    assert set(df["scenario"].unique()) == {"FD001", "FD002"}
    assert df.shape[0] == 2
