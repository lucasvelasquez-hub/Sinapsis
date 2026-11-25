"""Las métricas mostradas son las del modelo cargado, no las de una tabla que puede no existir."""

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.analytics import PredictionResult
from app.services.prediction_service import model_evaluation


def test_overview_reports_metrics_of_the_loaded_model(client: TestClient, db: Session) -> None:
    db.execute(delete(PredictionResult))  # p. ej. Supabase, donde nunca se entrenó

    body = client.get("/api/v1/analytics/overview").json()

    assert body["selected_model"] == "hist_gradient_boosting_mae"
    metrics = {(m["model_name"], m["split_name"]): m for m in body["model_metrics"]}
    assert len(metrics) == 8
    # Cifras del artefacto cargado (no hardcodeadas: cambian con cada reentreno).
    _, rows = model_evaluation()
    expected_val = next(
        r
        for r in rows
        if r["model_name"] == "hist_gradient_boosting_mae" and r["split_name"] == "validation"
    )
    assert metrics[("hist_gradient_boosting_mae", "validation")]["mae"] == expected_val["mae"]
    assert metrics[("hist_gradient_boosting_mae", "validation")]["is_selected"] is True
    assert metrics[("linear_regression_ridge", "validation")]["is_selected"] is False
    baseline_test = next(
        r for r in rows if r["model_name"] == "statistical_baseline" and r["split_name"] == "test"
    )
    assert metrics[("statistical_baseline", "test")]["mae"] == baseline_test["mae"]
