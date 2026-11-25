"""Tests para la auditoría de reglas EMI y ablación comparativa (Task 3)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ablation_scoring.py"


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location("ablation_scoring", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None, f"No existe {SCRIPT_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_run_ablation_compares_reference_greedy_and_core(db: Session) -> None:
    mod = _load_script()
    out = mod.run_ablation(db)

    names = [row["strategy"] for row in out["strategies"]]
    assert "REFERENCIA_DESPACHADOR" in names
    assert "GREEDY_ETA" in names
    assert "CORE_ACTUAL" in names

    for row in out["strategies"]:
        assert row["total_requests"] == 58
        assert row["avg_eta_min"] is not None
        assert 0.0 <= row["sla_pct"] <= 100.0
        assert row["workload_cv"] is not None

    audit = out["rule_audit"]
    assert audit["total_requests"] == 58
    assert audit["r01_incompatible_count"] == 0
    assert audit["r03_vital_without_ambulance_or_pair"] == 0
    assert "d03_green_uncovered_warnings" in audit
    assert "d05_tam_on_02_warnings" in audit
