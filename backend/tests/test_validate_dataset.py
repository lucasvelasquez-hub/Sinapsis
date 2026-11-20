"""Validador del dataset de data/raw (scripts/validate_dataset.py)."""

import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from validate_dataset import findings, validate  # noqa: E402


def test_validate_dataset_accepts_data_raw() -> None:
    assert validate(RAW_DIR) == []


def test_findings_report_known_quality_issues() -> None:
    f = findings(RAW_DIR)

    assert f["night_shift_daytime_assignments"] == 11
    assert f["overlaps"] == 0


def test_validate_dataset_flags_missing_column(tmp_path: Path) -> None:
    for csv in RAW_DIR.glob("*.csv"):
        shutil.copy(csv, tmp_path / csv.name)
    services = pd.read_csv(tmp_path / "services.csv", encoding="utf-8-sig")
    services.drop(columns=["closure_datetime"]).to_csv(tmp_path / "services.csv", index=False)

    assert any("closure_datetime" in p for p in validate(tmp_path))


def test_validate_dataset_flags_ineligible_assignment(tmp_path: Path) -> None:
    for csv in RAW_DIR.glob("*.csv"):
        shutil.copy(csv, tmp_path / csv.name)
    services = pd.read_csv(tmp_path / "services.csv", encoding="utf-8-sig")
    services.loc[0, ["service_type", "assigned_unit_id"]] = ["EVENTO_ESPECIAL", "MOV-001"]
    services.to_csv(tmp_path / "services.csv", index=False)

    assert any("no elegible" in p for p in validate(tmp_path))
