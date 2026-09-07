"""Configuración central de rutas del proyecto ETL."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
CURATED_DIR = BASE_DIR / "data" / "curated"

# Columnas del dataset NASA Turbofan (CMAPSS):
# id_motor, ciclo, 3 settings operacionales, 21 sensores
COLUMNS = [
    "id", "cycle", "op1", "op2", "op3",
    *[f"s{i}" for i in range(1, 22)],
]

# Ventana (en ciclos) para etiquetar fallo inminente
RUL_THRESHOLD = 30
