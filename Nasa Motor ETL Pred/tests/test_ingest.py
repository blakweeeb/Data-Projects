"""Pruebas de ingesta, incluyendo validación de formato NASA CMAPSS."""

from pathlib import Path

import pandas as pd
import pytest

from src.ingest import ingest
from src.config import RAW_DIR


def test_ingest_archivo_malo_lanza_error(tmp_path):
    bad = tmp_path / "RUL_FD001.txt"
    bad.write_text("112\n98\n69\n")
    with pytest.raises(ValueError, match="26 columnas"):
        ingest(bad)


def test_ingest_formato_correcto(tmp_path):
    good = tmp_path / "FD001_train.txt"
    row = "1 1 " + " ".join(["1.0"] * 24)
    good.write_text(row + "\n" + row + "\n")
    out = tmp_path / "out.parquet"
    df = ingest(good, out)
    assert df.shape == (2, 26)
    assert list(df.columns)[:2] == ["id", "cycle"]
