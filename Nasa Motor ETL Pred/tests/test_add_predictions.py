"""Prueba para la adición de predicciones al dataset del dashboard."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.add_predictions import build, FEATURES
from src.config import CURATED_DIR


def test_build_agrega_predicciones(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    curated = tmp_path / "data" / "curated"
    curated.mkdir(parents=True)
    raw = tmp_path / "data" / "raw"
    for fd in ["FD001", "FD002", "FD003", "FD004"]:
        df = pd.DataFrame({
            "id": [1, 1], "cycle": [1, 2], "op1": [1.0, 1.0], "op2": [1.0, 1.0],
            "op3": [1.0, 1.0], **{f"s{i}": [1.0, 1.0] for i in range(1, 22)},
            "rul": [2, 1], "label": [0, 0],
        })
        df.to_parquet(curated / f"train_{fd}.parquet", index=False)
        (raw / f"RUL_{fd}.txt").write_text("5\n")
        t = pd.DataFrame({
            "id": [1], "cycle": [1], "op1": [1.0], "op2": [1.0], "op3": [1.0],
            **{f"s{i}": [1.0] for i in range(1, 22)}, "rul": [0], "label": [0],
        })
        t.to_parquet(curated / f"test_{fd}.parquet", index=False)

    import joblib
    from sklearn.dummy import DummyRegressor
    from src.config import BASE_DIR
    dummy = DummyRegressor(strategy="constant", constant=10.0)
    dummy.fit(np.zeros((2, len(FEATURES))), np.array([0.0, 0.0]))
    joblib.dump(dummy, models / "modelo_rul.joblib")

    import src.add_predictions as ap
    ap.MODELS = models
    ap.CURATED_DIR = curated
    ap.RAW_DIR = raw

    out = curated / "dashboard_data.parquet"
    res = build(out)
    assert "rul_predicho" in res.columns
    assert "conjunto" in res.columns
    assert set(res["conjunto"].unique()) == {"train", "test"}

    test_row = res[res["conjunto"] == "test"].iloc[0]
    assert test_row["rul"] == 5
    assert test_row["rul_predicho"] == 10.0
