"""El artefacto ML se valida contra el código que lo usa."""

import pickle
from pathlib import Path

import pytest
import sklearn

from app.ml.artifact import ArtifactIncompatibleError, load_artifact
from app.ml.features import FEATURE_COLUMNS


def _write(tmp_path: Path, artifact: dict) -> Path:
    path = tmp_path / "artifact.pkl"
    path.write_bytes(pickle.dumps(artifact))
    return path


def _manifest(**overrides: object) -> dict:
    return {
        "format_version": 2,
        "sklearn_version": sklearn.__version__,
        "feature_columns": list(FEATURE_COLUMNS),
        **overrides,
    }


def test_load_artifact_without_manifest_is_incompatible(tmp_path: Path) -> None:
    path = _write(tmp_path, {"selected_model_name": "statistical_baseline"})

    with pytest.raises(ArtifactIncompatibleError, match="manifest"):
        load_artifact(path)


def test_load_artifact_other_sklearn_version_is_incompatible(tmp_path: Path) -> None:
    path = _write(tmp_path, {"manifest": _manifest(sklearn_version="0.0.1")})

    with pytest.raises(ArtifactIncompatibleError, match="scikit-learn"):
        load_artifact(path)


def test_load_artifact_other_features_is_incompatible(tmp_path: Path) -> None:
    path = _write(tmp_path, {"manifest": _manifest(feature_columns=["hour_of_day"])})

    with pytest.raises(ArtifactIncompatibleError, match="features"):
        load_artifact(path)


def test_load_artifact_compatible(tmp_path: Path) -> None:
    path = _write(tmp_path, {"manifest": _manifest(), "selected_model_name": "x"})

    assert load_artifact(path)["selected_model_name"] == "x"


def test_load_artifact_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_artifact(tmp_path / "nope.pkl") is None


def test_committed_artifact_is_compatible() -> None:
    from app.services.prediction_service import ARTIFACT_PATH

    assert load_artifact(ARTIFACT_PATH) is not None
