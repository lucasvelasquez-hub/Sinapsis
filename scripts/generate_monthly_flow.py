"""Genera un flujo SIMULADO de solicitudes para un mes, a partir del histórico de data/raw.

Método (bootstrap condicional, sin acceso a la base de datos):

1. Volumen diario: nivel medio del histórico × factor del día de la semana. Los festivos se
   tratan como domingo (el histórico muestra el mismo nivel; es también el tipo de día
   `DOMINGO_FESTIVO` de los factores de tráfico). Cada día se sortea con una binomial negativa
   cuya dispersión se estima del histórico, porque la variación diaria supera a la de Poisson.
   No se extrapola tendencia: el histórico (46 días) muestra un escalón, no una pendiente estable.
2. Cada solicitud copia los atributos de una solicitud histórica del mismo grupo de día
   (laboral / fin de semana o festivo): hora, zona, canal y el triaje inicial (urgencia, motivo y
   discriminador). Así se conservan las combinaciones clínicamente coherentes y la relación con
   la hora. Minuto y segundo se sortean dentro de esa hora.

Solo genera la demanda (lo que llega a la central): asignaciones y tiempos los produce el
sistema al despachar, con decisión humana. Cada registro es compatible con
`POST /api/v1/requests/simulate` y guarda en `origen_historico` el servicio del que se copió.

Uso (desde backend/):
    uv run python ../scripts/generate_monthly_flow.py --month 2026-11 --seed 42
"""

from __future__ import annotations

import argparse
import calendar
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_SERVICES = ROOT_DIR / "data" / "raw" / "01_servicios_historicos.json"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

# Festivos de Colombia 2026 (Ley Emiliani aplicada). Solo hay calendario para 2026.
FESTIVOS_CO_2026 = frozenset(
    date(2026, m, d)
    for m, d in [
        (1, 1), (1, 12), (3, 23), (4, 2), (4, 3), (5, 1), (5, 18), (6, 8), (6, 15),
        (6, 29), (7, 20), (8, 7), (8, 17), (10, 12), (11, 2), (11, 16), (12, 8), (12, 25),
    ]
)  # fmt: skip
SUPPORTED_YEAR = 2026

DOMINGO_FESTIVO = 6  # clase de día: 0..5 = lunes..sábado, 6 = domingo o festivo
LABORAL = "LABORAL"
FIN_DE_SEMANA_FESTIVO = "FIN_DE_SEMANA_FESTIVO"


def day_class(d: date) -> int:
    """0..5 = lunes..sábado; 6 = domingo o festivo."""
    return DOMINGO_FESTIVO if d in FESTIVOS_CO_2026 else min(d.weekday(), DOMINGO_FESTIVO)


def day_group(d: date) -> str:
    """Grupo del perfil horario: laboral (L-V no festivo) o fin de semana/festivo."""
    return LABORAL if day_class(d) <= 4 else FIN_DE_SEMANA_FESTIVO


def load_history(path: Path = RAW_SERVICES) -> pd.DataFrame:
    """Una fila por servicio histórico con el triaje INICIAL (lo que llega a la central)."""
    services = json.loads(path.read_text(encoding="utf-8"))["servicios"]
    rows = []
    for s in services:
        first = s["clasificaciones"][0]
        rows.append(
            {
                "service_id": s["id_servicio"],
                "ts": datetime.fromisoformat(s["fecha_hora_solicitud"]),
                "zone_id": s["id_zona"],
                "channel": s["canal"],
                "urgency_level": first["codigo"],
                "service_type": first["motivo_consulta"],
                "discriminator": first["discriminador"],
            }
        )
    df = pd.DataFrame(rows)
    df["date"] = df["ts"].dt.date
    df["hour"] = df["ts"].dt.hour
    df["group"] = df["date"].map(day_group)
    return df


def volume_model(history: pd.DataFrame) -> dict[str, Any]:
    """Nivel medio, factor por clase de día y dispersión (k) de la binomial negativa."""
    daily = history.groupby("date").size()
    level = float(daily.mean())
    classes = pd.Series([day_class(d) for d in daily.index], index=daily.index)
    class_mean = daily.groupby(classes).mean()
    factors = {int(c): float(class_mean[c] / level) for c in class_mean.index}
    expected = classes.map(class_mean)
    resid_var = float(((daily - expected) ** 2).mean())
    # var = mu + mu^2 / k  ->  k = mu^2 / (var - mu). Sin sobredispersión: Poisson (k = inf).
    k = level**2 / (resid_var - level) if resid_var > level else float("inf")
    return {"level": level, "factors": factors, "k": k, "days": len(daily)}


def _none_if_missing(value: Any) -> Any:
    """pandas convierte los nulos del JSON en NaN; el flujo los devuelve como null."""
    return None if pd.isna(value) else value


def _draw_count(rng: np.random.Generator, mu: float, k: float) -> int:
    if np.isinf(k):
        return int(rng.poisson(mu))
    return int(rng.poisson(rng.gamma(shape=k, scale=mu / k)))


def generate_flow(year: int, month: int, seed: int = 42, raw_path: Path = RAW_SERVICES) -> dict:
    if year != SUPPORTED_YEAR:
        raise ValueError(f"Solo hay calendario de festivos para {SUPPORTED_YEAR}")
    rng = np.random.default_rng(seed)
    history = load_history(raw_path)
    model = volume_model(history)
    pools = {g: frame.reset_index(drop=True) for g, frame in history.groupby("group")}
    attrs = ["service_id", "hour", "zone_id", "channel", "urgency_level", "service_type"]
    attrs.append("discriminator")

    requests: list[dict[str, Any]] = []
    days: list[dict[str, Any]] = []
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        d = date(year, month, day)
        cls = day_class(d)
        mu = model["level"] * model["factors"][cls]
        n = _draw_count(rng, mu, model["k"])
        pool = pools[day_group(d)]
        picks = pool.iloc[rng.integers(0, len(pool), size=n)][attrs]
        offsets = rng.integers(0, 3600, size=n)
        for rec, offset in zip(picks.itertuples(index=False), offsets, strict=True):
            ts = datetime(year, month, day, rec.hour) + timedelta(seconds=int(offset))
            requests.append(
                {
                    "request_datetime": ts.isoformat(),
                    "urgency_level": rec.urgency_level,
                    "service_type": rec.service_type,
                    "discriminator": _none_if_missing(rec.discriminator),
                    "channel": _none_if_missing(rec.channel),
                    "zone_id": rec.zone_id,
                    "origen_historico": rec.service_id,
                }
            )
        days.append(
            {
                "fecha": d.isoformat(),
                "festivo": d in FESTIVOS_CO_2026,
                "esperadas": round(mu, 1),
                "generadas": n,
            }
        )

    requests.sort(key=lambda r: (r["request_datetime"], r["origen_historico"]))
    for i, r in enumerate(requests, start=1):
        r["id_flujo"] = f"FLU-{year}{month:02d}-{i:05d}"

    return {
        "_aviso": (
            "SIMULADO. Flujo generado por bootstrap condicional sobre datos ficticios "
            "(EstudIA); no es operación real ni un pronóstico."
        ),
        "mes": f"{year}-{month:02d}",
        "semilla": seed,
        "fuente": {
            "archivo": raw_path.name,
            "desde": history["date"].min().isoformat(),
            "hasta": history["date"].max().isoformat(),
            "dias": model["days"],
            "servicios": len(history),
        },
        "modelo_volumen": {
            "nivel_medio_dia": round(model["level"], 1),
            "factor_por_dia": {
                ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo_festivo"][
                    c
                ]: round(f, 3)
                for c, f in sorted(model["factors"].items())
            },
            "dispersion_k": round(model["k"], 1),
        },
        "festivos_del_mes": sorted(
            d.isoformat() for d in FESTIVOS_CO_2026 if (d.year, d.month) == (year, month)
        ),
        "total_solicitudes": len(requests),
        "dias": days,
        "validacion": compare_with_history(history, requests),
        "solicitudes": [
            {"id_flujo": r.pop("id_flujo"), **r} for r in requests
        ],  # id_flujo primero, para leerlo mejor
    }


def compare_with_history(history: pd.DataFrame, requests: list[dict]) -> dict[str, Any]:
    """Distancias entre el flujo generado y el histórico (puntos porcentuales)."""
    gen = pd.DataFrame(requests)
    gen_ts = pd.to_datetime(gen["request_datetime"])

    def share(series: pd.Series) -> pd.Series:
        return series.value_counts(normalize=True) * 100

    def max_diff(a: pd.Series, b: pd.Series) -> float:
        return round(float(a.sub(b, fill_value=0).abs().max()), 2)

    def total_variation(a: pd.Series, b: pd.Series) -> float:
        return round(float(a.sub(b, fill_value=0).abs().sum() / 2), 2)

    hist_daily = history.groupby("date").size()
    gen_daily = gen_ts.dt.date.value_counts()
    return {
        "media_dia_historico": round(float(hist_daily.mean()), 1),
        "media_dia_generado": round(float(gen_daily.mean()), 1),
        "urgencia_pct_historico": share(history["urgency_level"]).round(1).to_dict(),
        "urgencia_pct_generado": share(gen["urgency_level"]).round(1).to_dict(),
        "urgencia_max_dif_pp": max_diff(
            share(history["urgency_level"]), share(gen["urgency_level"])
        ),
        "hora_max_dif_pp": max_diff(share(history["hour"]), share(gen_ts.dt.hour)),
        "zona_variacion_total_pp": total_variation(
            share(history["zone_id"]), share(gen["zone_id"])
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--month", default="2026-11", help="AAAA-MM (por defecto 2026-11)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    year, month = (int(x) for x in args.month.split("-"))
    flow = generate_flow(year, month, seed=args.seed)
    out = args.out or PROCESSED_DIR / f"flujo_{year}_{month:02d}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # allow_nan=False: un NaN produciría JSON inválido que el endpoint rechaza.
    out.write_text(
        json.dumps(flow, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8"
    )

    v = flow["validacion"]
    print(f"{flow['total_solicitudes']} solicitudes para {flow['mes']} -> {out}")
    print(f"Media/día: histórico {v['media_dia_historico']} · generado {v['media_dia_generado']}")
    print(f"Urgencia (máx. dif.): {v['urgencia_max_dif_pp']} pp")
    print(f"Perfil horario (máx. dif.): {v['hora_max_dif_pp']} pp")
    print(f"Zonas (variación total): {v['zona_variacion_total_pp']} pp")
    print(f"Festivos: {', '.join(flow['festivos_del_mes']) or 'ninguno'}")


if __name__ == "__main__":
    main()
