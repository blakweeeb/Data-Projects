"""Conftest: asegura que la raíz del proyecto esté en sys.path para imports de 'src'."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
