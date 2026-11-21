"""Chronological ML evaluation & training for CORE MVP v1.0.

Evaluates:
1. Statistical Baseline (contextual historical median by urgency, service_type, zone)
2. Linear Regression (Ridge with OneHotEncoder)
3. Random Forest Regressor

Strict chronological split: 70% train, 15% validation, 15% test.
No temporal leakage: uses only features known at request_datetime.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import delete

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal, engine
from app.ml.artifact import build_manifest, save_artifact
from app.ml.baseline import ContextualStatisticalBaseline
from app.ml.features import (
    CATEGORICAL_COLUMNS,
    FEATURE_COLUMNS,
    NUMERIC_COLUMNS,
    build_feature_frame,
)
from app.models.analytics import PredictionResult

ARTIFACT_PATH = Path(__file__).resolve().parent / "model_artifact.pkl"


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    abs_err = np.abs(y_true - y_pred)
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "median_ae": round(float(np.median(abs_err)), 4),
        "p90_ae": round(float(np.percentile(abs_err, 90)), 4),
        "rmse": round(float(root_mean_squared_error(y_true, y_pred)), 4),
    }


def train_and_evaluate() -> dict:
    query = """
        SELECT
            s.service_id,
            s.request_datetime,
            s.urgency_level,
            s.service_type,
            s.zone_id,
            COALESCE(z.relative_demand, 'MEDIA') AS relative_demand,
            s.response_time_min,
            u.unit_type,
            u.base_id,
            u.shift,
            u.capacity,
            COALESCE(s.distance_km, tt.distance_km, 5.0) AS distance_km,
            COALESCE(tt.valley_time_min, 12.0) AS valley_time_min,
            COALESCE(tf.factor, 1.0) AS traffic_factor
        FROM raw.services s
        JOIN raw.units u ON s.assigned_unit_id = u.unit_id
        LEFT JOIN raw.zones z ON s.zone_id = z.zone_id
        LEFT JOIN raw.bases b ON u.base_id = b.base_id
        LEFT JOIN raw.zone_travel_times tt
            ON COALESCE(s.origin_zone_id, b.zone_id) = tt.origin_zone_id
            AND s.zone_id = tt.destination_zone_id
        LEFT JOIN raw.traffic_factors tf
            ON tf.day_type = (
                CASE
                    WHEN EXTRACT(ISODOW FROM s.request_datetime) <= 5 THEN 'LUNES_A_VIERNES'
                    WHEN EXTRACT(ISODOW FROM s.request_datetime) = 6 THEN 'SABADO'
                    ELSE 'DOMINGO_FESTIVO'
                END
            )
            AND EXTRACT(HOUR FROM s.request_datetime)::int BETWEEN tf.hour_start AND tf.hour_end
        WHERE s.response_time_min IS NOT NULL
        ORDER BY s.request_datetime ASC, s.service_id ASC
    """
    raw = pd.read_sql(query, engine)
    # Same feature construction as serving (prediction_service): no train/serve skew.
    df = build_feature_frame(raw.to_dict("records"))
    df["response_time_min"] = raw["response_time_min"].to_numpy()

    n = len(df)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    train_df = df.iloc[:train_end].copy()
    val_df = df.iloc[train_end:val_end].copy()
    test_df = df.iloc[val_end:].copy()

    cat_cols = CATEGORICAL_COLUMNS
    num_cols = NUMERIC_COLUMNS
    feature_cols = FEATURE_COLUMNS

    # 1. Statistical Baseline
    baseline = ContextualStatisticalBaseline()
    baseline.fit(train_df)
    base_val = compute_metrics(val_df["response_time_min"].to_numpy(), baseline.predict(val_df))
    base_test = compute_metrics(test_df["response_time_min"].to_numpy(), baseline.predict(test_df))

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
            ("num", "passthrough", num_cols),
        ]
    )

    # 2. Ridge Linear Regression
    lin_pipe = Pipeline([("prep", clone(preprocessor)), ("model", Ridge(alpha=1.0))])
    lin_pipe.fit(train_df[feature_cols], train_df["response_time_min"])
    lin_val = compute_metrics(
        val_df["response_time_min"].to_numpy(), lin_pipe.predict(val_df[feature_cols])
    )
    lin_test = compute_metrics(
        test_df["response_time_min"].to_numpy(), lin_pipe.predict(test_df[feature_cols])
    )

    # 3. Random Forest Regressor
    rf_pipe = Pipeline(
        [
            ("prep", preprocessor),
            (
                "model",
                RandomForestRegressor(n_estimators=120, max_depth=12, random_state=42, n_jobs=-1),
            ),
        ]
    )
    rf_pipe.fit(train_df[feature_cols], train_df["response_time_min"])
    rf_val = compute_metrics(
        val_df["response_time_min"].to_numpy(), rf_pipe.predict(val_df[feature_cols])
    )
    rf_test = compute_metrics(
        test_df["response_time_min"].to_numpy(), rf_pipe.predict(test_df[feature_cols])
    )

    candidates = [
        ("statistical_baseline", base_val, base_test, baseline),
        ("linear_regression_ridge", lin_val, lin_test, lin_pipe),
        ("random_forest_regressor", rf_val, rf_test, rf_pipe),
    ]

    # Select best on validation MAE; keep baseline if no ML model improves it
    best_name = "statistical_baseline"
    best_val_mae = base_val["mae"]
    for name, val_m, _, _ in candidates[1:]:
        if val_m["mae"] < best_val_mae - 0.05:
            best_val_mae = val_m["mae"]
            best_name = name

    candidates_val = [(name, val_m) for name, val_m, _, _ in candidates]
    candidates_test = [(name, test_m) for name, _, test_m, _ in candidates]
    now_utc = datetime.now(UTC).replace(tzinfo=None)
    with SessionLocal() as db:
        db.execute(delete(PredictionResult))
        for name, val_m, test_m, _ in candidates:
            is_sel = name == best_name
            db.add(
                PredictionResult(
                    model_name=name,
                    split_name="validation",
                    is_selected=is_sel,
                    evaluated_at=now_utc,
                    **val_m,
                )
            )
            db.add(
                PredictionResult(
                    model_name=name,
                    split_name="test",
                    is_selected=is_sel,
                    evaluated_at=now_utc,
                    **test_m,
                )
            )
        db.commit()

    artifact = {
        "selected_model_name": best_name,
        "baseline_data": baseline.to_dict(),
        "ml_model": rf_pipe
        if best_name == "random_forest_regressor"
        else (lin_pipe if best_name == "linear_regression_ridge" else None),
        "feature_cols": feature_cols,
        "trained_at": now_utc.isoformat(),
        "manifest": build_manifest(
            trained_at=now_utc.isoformat(),
            metrics={
                "selected": best_name,
                "validation": dict(candidates_val),
                "test": dict(candidates_test),
            },
        ),
    }
    save_artifact(ARTIFACT_PATH, artifact)

    summary = {
        "selected_model": best_name,
        "validation": {name: val_m for name, val_m, _, _ in candidates},
        "test": {name: test_m for name, _, test_m, _ in candidates},
    }
    return summary


if __name__ == "__main__":
    res = train_and_evaluate()
    print("Model Evaluation Summary:")
    print(f"Selected: {res['selected_model']}")
    for split in ("validation", "test"):
        print(f"--- {split.upper()} ---")
        for mname, metrics in res[split].items():
            print(f"  {mname}: {metrics}")
