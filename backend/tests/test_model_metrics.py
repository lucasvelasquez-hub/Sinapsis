"""Las métricas mostradas son las del modelo cargado, no las de una tabla que puede no existir."""

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.analytics import PredictionResult


def test_overview_reports_metrics_of_the_loaded_model(client: TestClient, db: Session) -> None:
    db.execute(delete(PredictionResult))  # p. ej. Supabase, donde nunca se entrenó

    body = client.get("/api/v1/analytics/overview").json()

    assert body["selected_model"] == "linear_regression_ridge"
    metrics = {(m["model_name"], m["split_name"]): m for m in body["model_metrics"]}
    assert len(metrics) == 6
    assert metrics[("linear_regression_ridge", "validation")]["mae"] == 4.2111
    assert metrics[("linear_regression_ridge", "validation")]["is_selected"] is True
    assert metrics[("statistical_baseline", "test")]["mae"] == 3.6898
