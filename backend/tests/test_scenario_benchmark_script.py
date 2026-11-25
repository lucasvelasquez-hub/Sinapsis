"""Tests para el script reproducible de evaluación de los 14 escenarios EMI."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_scenarios.py"


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location("evaluate_scenarios", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None, f"No existe {SCRIPT_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_benchmark_report_covers_all_14_scenarios_and_58_requests(db: Session) -> None:
    mod = _load_script()
    report = mod.build_benchmark_report(db)

    totals = report["totals"]
    assert totals["total_scenarios"] == 14
    assert totals["total_requests"] == 58
    assert 0.0 <= totals["type_match_rate"] <= 1.0
    assert 0.0 <= totals["unit_match_rate"] <= 1.0
    assert totals["avg_eta_core_min"] is not None
    assert totals["avg_eta_ref_min"] is not None
    assert totals["eta_delta_min"] is not None
    assert 0.0 <= totals["sla_core_pct"] <= 100.0
    assert 0.0 <= totals["sla_ref_pct"] <= 100.0
    assert sum(totals["discrepancy_counts"].values()) == 58

    assert len(report["scenarios"]) == 14
    assert len(report["kpis"]) == 12
    assert len(report["requests"]) == 58

    # Debe ser completamente serializable a JSON
    encoded = json.dumps(report, ensure_ascii=False)
    assert "ESC-01" in encoded
    assert "ESC-14" in encoded


def test_render_markdown_report_contains_key_sections(db: Session) -> None:
    mod = _load_script()
    report = mod.build_benchmark_report(db)
    md = mod.render_markdown_report(report)

    assert "# Reporte de Benchmark — 14 Escenarios de Referencia EMI" in md
    assert "ESC-01" in md
    assert "ESC-14" in md
    assert "KPI-01" in md
    assert "KPI-12" in md
    assert "Desglose de Discrepancias" in md
