"""Model artifact I/O with a manifest checked against the running code.

An artifact trained with another scikit-learn version or another feature set can
predict silently wrong values, so it is rejected instead of used.
"""

import pickle
from pathlib import Path
from typing import Any

import sklearn

from app.ml.features import FEATURE_COLUMNS

FORMAT_VERSION = 2


class ArtifactIncompatibleError(RuntimeError):
    """The artifact does not match this code: retrain with app/ml/train_models.py."""


def build_manifest(trained_at: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "sklearn_version": sklearn.__version__,
        "feature_columns": list(FEATURE_COLUMNS),
        "trained_at": trained_at,
        "metrics": metrics,
    }


def save_artifact(path: Path, artifact: dict[str, Any]) -> None:
    if "manifest" not in artifact:
        raise ValueError("artifact needs a manifest (build_manifest)")
    with path.open("wb") as f:
        pickle.dump(artifact, f)


def load_artifact(path: Path) -> dict[str, Any] | None:
    """Load and validate; None when no artifact exists (fallback predictions)."""
    if not path.exists():
        return None
    with path.open("rb") as f:
        artifact = pickle.load(f)  # trusted, repo-local file

    manifest = artifact.get("manifest")
    hint = "Retrain: cd backend && uv run python app/ml/train_models.py"
    if not manifest or manifest.get("format_version") != FORMAT_VERSION:
        raise ArtifactIncompatibleError(f"{path.name}: missing or outdated manifest. {hint}")
    if manifest.get("sklearn_version") != sklearn.__version__:
        raise ArtifactIncompatibleError(
            f"{path.name}: trained with scikit-learn {manifest.get('sklearn_version')},"
            f" running {sklearn.__version__}. {hint}"
        )
    if manifest.get("feature_columns") != list(FEATURE_COLUMNS):
        raise ArtifactIncompatibleError(
            f"{path.name}: features differ from app/ml/features.py. {hint}"
        )
    return artifact
