"""Pruebas unitarias de transformación."""

import pandas as pd

from src.transform import add_rul_pandas


def test_add_rul_pandas():
    df = pd.DataFrame({"id": [1, 1, 1], "cycle": [1, 20, 40]})
    out = add_rul_pandas(df)
    assert out["rul"].tolist() == [39, 20, 0]
    assert out["label"].tolist() == [0, 1, 1]


def test_add_rul_multiples_motores():
    df = pd.DataFrame({"id": [1, 1, 2, 2], "cycle": [1, 5, 1, 10]})
    out = add_rul_pandas(df)
    assert out[out["id"] == 1]["rul"].tolist() == [4, 0]
    assert out[out["id"] == 2]["rul"].tolist() == [9, 0]
