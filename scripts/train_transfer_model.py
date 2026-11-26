"""Entrena y calibra el modelo predictivo de probabilidad de traslado (Regla D06).

Lee por defecto desde PostgreSQL/Supabase (DATABASE_URL en backend/.env) y usa
data/raw/01_servicios_historicos.json como respaldo automático si no hay BD disponible.
"""

import argparse
import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "backend" / ".env"
RAW_JSON_PATH = ROOT / "data" / "raw" / "01_servicios_historicos.json"
ARTIFACT_PATH = ROOT / "backend" / "app" / "ml" / "transfer_artifact.pkl"

CAT_COLS = [
    "urgency_level",
    "manchester_scale",
    "service_type",
    "discriminator",
    "triage_combo",
    "channel",
    "zone_id",
]
NUM_COLS = ["hour", "is_weekend"]


def _initial_triage(clasificaciones: object) -> dict[str, str]:
    """Extrae únicamente la primera clasificación (secuencia 1) para evitar data leakage."""
    if not isinstance(clasificaciones, list) or not clasificaciones:
        return {}
    first = min(
        (c for c in clasificaciones if isinstance(c, dict)),
        key=lambda c: c.get("secuencia", 999),
        default={},
    )
    return {
        "manchester_scale": first.get("escala_manchester"),
        "service_type": first.get("motivo_consulta"),
        "discriminator": first.get("discriminador"),
    }


def load_from_db(db_url: str) -> pd.DataFrame:
    engine = create_engine(db_url)
    query = text("""
        SELECT
            service_id,
            request_datetime,
            urgency_level,
            manchester_scale,
            service_type,
            discriminator,
            channel,
            zone_id,
            required_transfer
        FROM raw.services
        WHERE is_synthetic = FALSE
          AND closure_state IN ('TRASLADADO', 'ATENDIDO_EN_SITIO')
          AND required_transfer IS NOT NULL
        ORDER BY request_datetime ASC, service_id ASC
    """)
    df = pd.read_sql(query, engine)
    df["required_transfer"] = df["required_transfer"].astype(bool).astype(int)
    df["request_datetime"] = pd.to_datetime(df["request_datetime"])
    return df.reset_index(drop=True)


def load_from_raw_json(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el dataset local en: {path}")

    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    records = payload["servicios"] if isinstance(payload, dict) and "servicios" in payload else payload
    df = pd.DataFrame(records)

    triage_df = pd.DataFrame(df["clasificaciones"].apply(_initial_triage).tolist(), index=df.index)
    df["service_id"] = df["id_servicio"]
    df["urgency_level"] = df["clasificacion_inicial"]
    df["manchester_scale"] = triage_df["manchester_scale"]
    df["service_type"] = triage_df["service_type"]
    df["discriminator"] = triage_df["discriminator"]
    df["channel"] = df["canal"]
    df["zone_id"] = df["id_zona"]

    valid_states = {"TRASLADADO", "ATENDIDO_EN_SITIO"}
    valid = df[df["estado_cierre"].isin(valid_states) & df["requirio_traslado"].notna()].copy()
    valid["required_transfer"] = valid["requirio_traslado"].astype(bool).astype(int)
    valid["request_datetime"] = pd.to_datetime(valid["fecha_hora_solicitud"])
    return valid.sort_values(["request_datetime", "service_id"]).reset_index(drop=True)


def load_dataset(source: str) -> tuple[pd.DataFrame, str]:
    load_dotenv(ENV_PATH)
    db_url = os.getenv("DATABASE_URL")

    if source == "raw":
        return load_from_raw_json(RAW_JSON_PATH), "RAW_JSON"

    if source == "db":
        if not db_url:
            raise RuntimeError("DATABASE_URL no está definido en backend/.env")
        return load_from_db(db_url), "POSTGRES_DB"

    # Modo 'auto': intenta BD desde .env y cae a data/raw si no hay conexión
    if db_url:
        try:
            return load_from_db(db_url), "POSTGRES_DB"
        except Exception as exc:
            print(f"[AVISO] No se pudo conectar a DATABASE_URL ({exc}); usando respaldo local data/raw...")

    return load_from_raw_json(RAW_JSON_PATH), "RAW_JSON_FALLBACK"


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    dt = df["request_datetime"]
    out["hour"] = dt.dt.hour
    out["is_weekend"] = (dt.dt.day_of_week >= 5).astype(int)

    for col in ["urgency_level", "manchester_scale", "service_type", "discriminator", "channel", "zone_id"]:
        out[col] = df[col].fillna("MISSING").astype(str)

    out["triage_combo"] = (
        out["urgency_level"] + "|" + out["service_type"] + "|" + out["discriminator"]
    )
    return out[CAT_COLS + NUM_COLS]


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrena el modelo de traslado D06.")
    parser.add_argument(
        "--source",
        choices=["auto", "db", "raw"],
        default="auto",
        help="Fuente de datos: auto (BD con fallback a raw), db o raw.",
    )
    args = parser.parse_args()

    df, used_source = load_dataset(args.source)
    print(f"Fuente de datos: {used_source} | Registros válidos: {len(df)}")

    X = build_features(df)
    y = df["required_transfer"].to_numpy()

    # Split cronológico 70 / 15 / 15
    n = len(df)
    i_train = int(n * 0.70)
    i_val = int(n * 0.85)

    X_train, y_train = X.iloc[:i_train], y[:i_train]
    X_val, y_val = X.iloc[i_train:i_val], y[i_train:i_val]
    X_test, y_test = X.iloc[i_val:], y[i_val:]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5), CAT_COLS),
            ("num", "passthrough", NUM_COLS),
        ]
    )

    model = Pipeline(
        [
            ("prep", preprocessor),
            ("clf", LogisticRegression(C=0.25, max_iter=1000, random_state=42)),
        ]
    )
    model.fit(X_train, y_train)

    val_probs = model.predict_proba(X_val)[:, 1]
    best_thresh, best_f1 = 0.35, 0.0
    for th in np.arange(0.15, 0.75, 0.05):
        score = f1_score(y_val, (val_probs >= th).astype(int), zero_division=0)
        if score > best_f1:
            best_f1 = score
            best_thresh = float(round(th, 2))

    mask_val_07 = (X_val["urgency_level"] == "07").to_numpy()
    d06_threshold = (
        round(float(np.quantile(val_probs[mask_val_07], 0.65)), 4)
        if mask_val_07.sum() > 0
        else 0.16
    )

    test_probs = model.predict_proba(X_test)[:, 1]
    test_preds = (test_probs >= best_thresh).astype(int)

    mask_07 = (X_test["urgency_level"] == "07").to_numpy()
    auc_07 = (
        round(float(roc_auc_score(y_test[mask_07], test_probs[mask_07])), 4)
        if mask_07.sum() > 0 and len(np.unique(y_test[mask_07])) > 1
        else None
    )

    metrics = {
        "model_name": "logistic_regression_l2_triage",
        "data_source": used_source,
        "threshold": best_thresh,
        "d06_threshold_07": d06_threshold,
        "val_f1": round(float(best_f1), 4),
        "test_roc_auc": round(float(roc_auc_score(y_test, test_probs)), 4),
        "test_pr_auc": round(float(average_precision_score(y_test, test_probs)), 4),
        "test_precision": round(float(precision_score(y_test, test_preds, zero_division=0)), 4),
        "test_recall": round(float(recall_score(y_test, test_preds, zero_division=0)), 4),
        "test_f1": round(float(f1_score(y_test, test_preds, zero_division=0)), 4),
        "test_07_roc_auc": auc_07,
        "train_rows": len(X_train),
        "val_rows": len(X_val),
        "test_rows": len(X_test),
    }
    print("Métricas Test (split cronológico):", metrics)

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "threshold": best_thresh,
            "d06_threshold_07": d06_threshold,
            "metrics": metrics,
        },
        ARTIFACT_PATH,
    )
    print(f"Artefacto guardado en: {ARTIFACT_PATH}")


if __name__ == "__main__":
    main()