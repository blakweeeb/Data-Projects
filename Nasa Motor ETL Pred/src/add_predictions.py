"""Añade predicciones del modelo RUL al dataset para Power BI."""

from pathlib import Path

import numpy as np
import pandas as pd
import joblib

from src.config import BASE_DIR, CURATED_DIR, RAW_DIR

MODELS = BASE_DIR / "models"
FEATURES = ["op1", "op2", "op3"] + [f"s{i}" for i in range(1, 22)]
OUT = CURATED_DIR / "dashboard_data.parquet"


def build(out: Path = OUT) -> pd.DataFrame:
    reg = joblib.load(MODELS / "modelo_rul.joblib")

    frames = []
    # Entrenamiento: RUL ya es correcta
    for f in sorted(CURATED_DIR.glob("train_FD00*.parquet")):
        df = pd.read_parquet(f).copy()
        df["scenario"] = f.stem.replace("train_", "")
        df["conjunto"] = "train"
        frames.append(df)

    # Test: reconstruir RUL real con RUL_FD00X.txt (el motor no llega a falla)
    for fd in ["FD001", "FD002", "FD003", "FD004"]:
        t = pd.read_parquet(CURATED_DIR / f"test_{fd}.parquet")
        rul_truth = np.atleast_1d(np.loadtxt(RAW_DIR / f"RUL_{fd}.txt"))
        parts = []
        for i, mid in enumerate(t["id"].unique()):
            sub = t[t["id"] == mid].copy()
            last = sub["cycle"].max()
            sub["rul"] = int(rul_truth[i]) + (last - sub["cycle"])
            sub["label"] = (sub["rul"] <= 30).astype(int)
            parts.append(sub)
        tt = pd.concat(parts, ignore_index=True)
        tt["scenario"] = fd
        tt["conjunto"] = "test"
        frames.append(tt)

    df = pd.concat(frames, ignore_index=True)
    df["rul_predicho"] = reg.predict(df[FEATURES]).round(1)
    df["error"] = (df["rul_predicho"] - df["rul"]).round(1)

    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    rmse_test = float(
        ((df[df["conjunto"] == "test"]["error"] ** 2).mean()) ** 0.5
    )
    print(f"[add_predictions] {len(df)} filas -> {out}")
    print(f"RMSE RUL (test, real vs predicho): {rmse_test:.2f} ciclos")
    return df


if __name__ == "__main__":
    build()
