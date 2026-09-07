"""Validaciones estaticas del proyecto dbt.

No requieren Docker, Trino ni dbt instalado: analizan el codigo fuente para
detectar los fallos que solo aparecen al ejecutar `dbt run` contra Trino 442.

Cubre tres cosas:
  1. Funciones que NO existen en Trino (initcap, datediff, nvl, ...).
  2. Dependencias rotas: todo ref()/source() debe apuntar a algo que exista.
  3. Nombres de modelo duplicados.

    pytest tests/ -v
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DBT_DIR = ROOT / "dbt"
MODELS_DIR = DBT_DIR / "models"
MACROS_DIR = DBT_DIR / "macros"
SEEDS_DIR = DBT_DIR / "seeds"

# funcion -> alternativa valida en Trino
FUNCIONES_PROHIBIDAS = {
    "initcap": "usar el macro {{ title_case('columna') }}",
    "datediff": "usar date_diff('day', inicio, fin)",
    "dateadd": "usar date_add('day', n, fecha)",
    "dayofweek": "usar day_of_week(fecha)",
    "nvl": "usar coalesce(a, b)",
    "ifnull": "usar coalesce(a, b)",
    "to_date": "usar cast(x as date)",
    "getdate": "usar current_timestamp",
    "substring_index": "usar split_part(cadena, sep, n)",
    "str_to_date": "usar date_parse(cadena, formato)",
}

COMENTARIO_JINJA = re.compile(r"\{#.*?#\}", re.DOTALL)
COMENTARIO_SQL = re.compile(r"--[^\n]*")


def _sql_models() -> list[Path]:
    return sorted(MODELS_DIR.rglob("*.sql"))


def _limpiar(texto: str) -> str:
    """Quita comentarios para no reportar falso positivos en la documentacion."""
    return COMENTARIO_SQL.sub(" ", COMENTARIO_JINJA.sub(" ", texto))


def _nombres_modelos() -> set[str]:
    nombres = {p.stem for p in MODELS_DIR.rglob("*.sql")}
    nombres |= {p.stem for p in SEEDS_DIR.glob("*.csv")}
    return nombres


# ---------------------------------------------------------------------------
# 1. Funciones inexistentes en Trino
# ---------------------------------------------------------------------------

def test_modelos_no_usan_funciones_inexistentes_en_trino():
    modelos = _sql_models() + sorted(MACROS_DIR.rglob("*.sql"))
    assert modelos, "No se encontraron modelos dbt"

    hallazgos: list[str] = []
    for ruta in modelos:
        codigo = _limpiar(ruta.read_text(encoding="utf-8"))
        for funcion, alternativa in FUNCIONES_PROHIBIDAS.items():
            patron = re.compile(rf"(?<![\w.'\}}]){funcion}\s*\(", re.IGNORECASE)
            for linea_num, linea in enumerate(codigo.splitlines(), start=1):
                if patron.search(linea):
                    hallazgos.append(
                        f"{ruta.relative_to(ROOT)}:{linea_num} usa {funcion.upper()}() -> {alternativa}"
                    )

    assert not hallazgos, "Funciones no soportadas por Trino:\n  " + "\n  ".join(hallazgos)


# ---------------------------------------------------------------------------
# 2. Dependencias resueltas
# ---------------------------------------------------------------------------

def test_todos_los_ref_apuntan_a_un_modelo_existente():
    disponibles = _nombres_modelos()
    rotos: list[str] = []

    for ruta in _sql_models() + sorted(DBT_DIR.joinpath("tests").rglob("*.sql")):
        codigo = _limpiar(ruta.read_text(encoding="utf-8"))
        for destino in re.findall(r"ref\(\s*['\"]([\w]+)['\"]\s*\)", codigo):
            if destino not in disponibles:
                rotos.append(f"{ruta.name}: ref('{destino}') no existe")

    assert not rotos, "Dependencias dbt rotas:\n  " + "\n  ".join(rotos)


def test_todos_los_source_estan_declarados():
    """Los source('raw', 'x') deben existir en sources.yml."""
    fuentes = MODELS_DIR / "staging" / "sources.yml"
    assert fuentes.exists(), "Falta dbt/models/staging/sources.yml"

    declarado = set(re.findall(r"-\s+name:\s*(\w+)", fuentes.read_text(encoding="utf-8")))
    # la primera coincidencia es el nombre del source en si ("raw")
    usados: set[str] = set()
    for ruta in _sql_models():
        codigo = _limpiar(ruta.read_text(encoding="utf-8"))
        usados |= set(re.findall(r"source\(\s*['\"]\w+['\"]\s*,\s*['\"](\w+)['\"]\s*\)", codigo))

    faltantes = sorted(usados - declarado)
    assert not faltantes, f"Tablas usadas como source pero no declaradas: {faltantes}"


# ---------------------------------------------------------------------------
# 3. Estructura
# ---------------------------------------------------------------------------

def test_no_hay_modelos_duplicados():
    nombres = [p.stem for p in MODELS_DIR.rglob("*.sql")]
    duplicados = sorted({n for n in nombres if nombres.count(n) > 1})
    assert not duplicados, f"Modelos duplicados: {duplicados}"


def test_macro_title_case_existe():
    """El macro title_case sustituye a INITCAP, que Trino no implementa."""
    macro = MACROS_DIR / "title_case.sql"
    assert macro.exists(), "Falta dbt/macros/title_case.sql"
    contenido = macro.read_text(encoding="utf-8")
    assert "array_join" in contenido and "transform" in contenido
