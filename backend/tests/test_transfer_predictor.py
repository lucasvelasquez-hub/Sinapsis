from datetime import datetime
from pathlib import Path

from app.services import transfer_predictor


def test_predict_transfer_with_trained_artifact() -> None:
    prob_flag, prob, source = transfer_predictor.predict_transfer_likelihood(
        request_datetime=datetime(2026, 11, 25, 14, 30),
        urgency_level="07",
        service_type="Disnea en adulto",
        discriminator="Fiebre con dificultad respiratoria leve",
        manchester_scale="VERDE",
        channel="TELEFONICO",
        zone_id="Z01",
    )
    assert source == "ML_TRANSFER_MODEL"
    assert prob is not None
    assert 0.0 <= prob <= 1.0
    assert isinstance(prob_flag, bool)


def test_predict_transfer_fallback_when_artifact_missing(monkeypatch) -> None:
    transfer_predictor._load_transfer_artifact.cache_clear()
    monkeypatch.setattr(transfer_predictor, "ARTIFACT_PATH", Path("/nonexistent/transfer.pkl"))

    flag_true, prob_none, source = transfer_predictor.predict_transfer_likelihood(
        request_datetime=datetime(2026, 11, 25, 14, 30),
        urgency_level="07",
        service_type="Caídas",
    )
    assert source == "RULE_FALLBACK"
    assert prob_none is None
    assert flag_true is True
    transfer_predictor._load_transfer_artifact.cache_clear()