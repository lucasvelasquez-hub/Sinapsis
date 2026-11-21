"""Validador del dataset real de Grupo EMI en data/raw (scripts/validate_dataset.py)."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from validate_dataset import validate  # noqa: E402


def test_validate_dataset_accepts_data_raw() -> None:
    assert validate(RAW_DIR) == []


def test_validate_dataset_flags_missing_file(tmp_path: Path) -> None:
    problems = validate(tmp_path)
    assert any("Falta el archivo requerido" in p for p in problems)
