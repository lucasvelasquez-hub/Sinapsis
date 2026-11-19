"""Deterministic synthetic dataset generator for CORE MVP v1.0.

Generates the 4 raw CSV files in data/raw/ with exact MVP dimensions:
- 10,000 services over 90 days
- 30 mobile units
- 15 compatibility rules
- 4 response targets

Does NOT include GPS, coordinates, or distances (by MVP scope).
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path
import random

import numpy as np

SEED = 42
ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"

ZONES = [f"ZONE-{i:02d}" for i in range(1, 9)]  # 8 operational zones
URGENCY_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
URGENCY_WEIGHTS = [0.15, 0.30, 0.35, 0.20]

SERVICE_TYPES = [
    "MEDICAL_CRITICAL",
    "TRAUMA_RESCUE",
    "MEDICAL_URGENT",
    "TRANSFER_ASSISTED",
    "CRISIS_INTERVENTION",
]
SERVICE_TYPE_WEIGHTS_BY_URGENCY = {
    "CRITICAL": [0.55, 0.35, 0.05, 0.00, 0.05],
    "HIGH": [0.20, 0.25, 0.40, 0.05, 0.10],
    "MEDIUM": [0.05, 0.10, 0.45, 0.25, 0.15],
    "LOW": [0.00, 0.05, 0.30, 0.50, 0.15],
}

UNIT_TYPES = ["ALS", "BLS", "RESCUE", "RAPID", "CRISIS"]
SHIFTS = ["MORNING", "AFTERNOON", "NIGHT", "FULL_24H"]

# Exactly 15 compatibility rules: (service_type, unit_type, priority_rank, min_capacity, notes)
COMPATIBILITY_RULES = [
    ("MEDICAL_CRITICAL", "ALS", 1, 2, "Soporte vital avanzado requerido para casos críticos"),
    ("MEDICAL_CRITICAL", "RAPID", 2, 1, "Unidad rápida de estabilización inicial"),
    ("MEDICAL_CRITICAL", "RESCUE", 3, 2, "Respaldo de rescate con soporte médico"),
    ("TRAUMA_RESCUE", "RESCUE", 1, 2, "Unidad principal de trauma y extricación"),
    ("TRAUMA_RESCUE", "ALS", 2, 2, "Soporte vital avanzado para trauma severo"),
    ("TRAUMA_RESCUE", "RAPID", 3, 1, "Primera respuesta rápida en trauma"),
    ("MEDICAL_URGENT", "BLS", 1, 1, "Soporte vital básico para urgencias médicas"),
    ("MEDICAL_URGENT", "ALS", 2, 1, "Soporte avanzado disponible para urgencias"),
    ("MEDICAL_URGENT", "RAPID", 3, 1, "Evaluación rápida en sitio"),
    ("TRANSFER_ASSISTED", "BLS", 1, 1, "Traslado asistido estándar"),
    ("TRANSFER_ASSISTED", "ALS", 2, 1, "Traslado asistido con monitoreo"),
    ("TRANSFER_ASSISTED", "CRISIS", 3, 1, "Traslado especializado de contención"),
    ("CRISIS_INTERVENTION", "CRISIS", 1, 1, "Equipo especializado en intervención en crisis"),
    ("CRISIS_INTERVENTION", "RAPID", 2, 1, "Contención inicial rápida"),
    ("CRISIS_INTERVENTION", "BLS", 3, 1, "Apoyo básico en crisis"),
]

RESPONSE_TARGETS = [
    ("CRITICAL", 8, 12, "P1 - Crítico", "Emergencia con riesgo vital inmediato"),
    ("HIGH", 15, 22, "P2 - Alto", "Urgencia alta que requiere atención prioritaria"),
    ("MEDIUM", 30, 45, "P3 - Medio", "Atención médica o traslado programado prioritario"),
    ("LOW", 60, 90, "P4 - Bajo", "Solicitud de baja complejidad o traslado diferible"),
]


def shift_covers_hour(shift: str, hour: int) -> bool:
    if shift == "FULL_24H":
        return True
    if shift == "MORNING":
        return 6 <= hour < 14
    if shift == "AFTERNOON":
        return 14 <= hour < 22
    if shift == "NIGHT":
        return hour >= 22 or hour < 6
    return False


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    np_rng = np.random.default_rng(SEED)

    # 1. response_targets.csv (4 rows)
    targets_path = RAW_DIR / "response_targets.csv"
    with targets_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["urgency_level", "target_response_min", "max_acceptable_min", "sla_label", "description"])
        writer.writerows(RESPONSE_TARGETS)

    # 2. service_rules.csv (15 rows)
    rules_path = RAW_DIR / "service_rules.csv"
    with rules_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rule_id", "service_type", "unit_type", "compatible", "priority_rank", "min_capacity", "notes"])
        for idx, (stype, utype, rank, min_cap, notes) in enumerate(COMPATIBILITY_RULES, start=1):
            writer.writerow([f"RULE-{idx:02d}", stype, utype, "true", rank, min_cap, notes])

    # 3. units.csv (30 rows)
    unit_type_pool = (
        ["ALS"] * 7
        + ["BLS"] * 9
        + ["RESCUE"] * 6
        + ["RAPID"] * 5
        + ["CRISIS"] * 3
    )
    shift_pool = (
        ["MORNING"] * 8
        + ["AFTERNOON"] * 8
        + ["NIGHT"] * 7
        + ["FULL_24H"] * 7
    )
    rng.shuffle(shift_pool)

    units = []
    for i in range(1, 31):
        utype = unit_type_pool[i - 1]
        shift = shift_pool[i - 1]
        cap = 2 if utype in ("ALS", "RESCUE") else 1
        units.append({
            "unit_id": f"UNIT-{i:02d}",
            "unit_code": f"M-{utype[:2]}-{i:02d}",
            "unit_type": utype,
            "base_zone_id": ZONES[(i - 1) % len(ZONES)],
            "shift": shift,
            "capacity": cap,
            "active": "true",
        })

    units_path = RAW_DIR / "units.csv"
    with units_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["unit_id", "unit_code", "unit_type", "base_zone_id", "shift", "capacity", "active"],
        )
        writer.writeheader()
        writer.writerows(units)

    # 4. services.csv (10,000 rows over 90 days)
    start_dt = datetime(2026, 8, 1, 0, 0, 0)
    total_seconds_90d = 90 * 24 * 3600

    # Generate 10,000 timestamps with realistic diurnal & zone distribution
    timestamps: list[datetime] = []
    hour_weights = np.array([
        0.5, 0.4, 0.35, 0.35, 0.4, 0.6,
        0.9, 1.2, 1.4, 1.5, 1.5, 1.6,
        1.5, 1.4, 1.4, 1.5, 1.6, 1.7,
        1.6, 1.4, 1.2, 1.0, 0.8, 0.6,
    ])
    hour_probs = hour_weights / hour_weights.sum()

    for _ in range(10_000):
        day_offset = int(np_rng.integers(0, 90))
        hour = int(np_rng.choice(24, p=hour_probs))
        minute = int(np_rng.integers(0, 60))
        second = int(np_rng.integers(0, 60))
        dt = start_dt + timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)
        timestamps.append(dt)

    timestamps.sort()

    compat_map: dict[str, list[str]] = {}
    for stype, utype, *_ in COMPATIBILITY_RULES:
        compat_map.setdefault(stype, []).append(utype)

    base_response_by_urgency = {
        "CRITICAL": 7.5,
        "HIGH": 13.0,
        "MEDIUM": 24.0,
        "LOW": 42.0,
    }
    base_duration_by_type = {
        "MEDICAL_CRITICAL": 48.0,
        "TRAUMA_RESCUE": 55.0,
        "MEDICAL_URGENT": 34.0,
        "TRANSFER_ASSISTED": 40.0,
        "CRISIS_INTERVENTION": 52.0,
    }
    zone_pressure_factor = {
        "ZONE-01": 1.15,
        "ZONE-02": 1.10,
        "ZONE-03": 1.00,
        "ZONE-04": 0.95,
        "ZONE-05": 1.05,
        "ZONE-06": 0.90,
        "ZONE-07": 1.08,
        "ZONE-08": 0.92,
    }
    zone_probs = [0.18, 0.16, 0.13, 0.11, 0.14, 0.09, 0.11, 0.08]

    services_path = RAW_DIR / "services.csv"
    with services_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "service_id",
            "request_datetime",
            "urgency_level",
            "service_type",
            "zone_id",
            "assigned_unit_id",
            "response_time_min",
            "service_duration_min",
            "completion_datetime",
            "status",
        ])

        for idx, req_dt in enumerate(timestamps, start=1):
            urgency = rng.choices(URGENCY_LEVELS, weights=URGENCY_WEIGHTS, k=1)[0]
            stype = rng.choices(SERVICE_TYPES, weights=SERVICE_TYPE_WEIGHTS_BY_URGENCY[urgency], k=1)[0]
            zone = rng.choices(ZONES, weights=zone_probs, k=1)[0]

            allowed_types = set(compat_map[stype])
            hour = req_dt.hour
            candidates = [
                u for u in units
                if u["unit_type"] in allowed_types and shift_covers_hour(u["shift"], hour)
            ]
            if not candidates:
                candidates = [u for u in units if u["unit_type"] in allowed_types]

            same_zone = [u for u in candidates if u["base_zone_id"] == zone]
            chosen_unit = rng.choice(same_zone if same_zone and rng.random() < 0.6 else candidates)

            # Response time model (deterministic statistical structure + realistic noise)
            peak_mult = 1.22 if (7 <= hour <= 10 or 17 <= hour <= 20) else (0.85 if hour < 5 else 1.0)
            same_zone_mult = 0.86 if chosen_unit["base_zone_id"] == zone else 1.08
            mean_resp = base_response_by_urgency[urgency] * zone_pressure_factor[zone] * peak_mult * same_zone_mult
            resp_min = float(np.clip(np_rng.gamma(shape=4.0, scale=mean_resp / 4.0), 2.0, 120.0))
            resp_min = round(resp_min, 2)

            mean_dur = base_duration_by_type[stype] * (1.1 if urgency == "CRITICAL" else 1.0)
            dur_min = float(np.clip(np_rng.gamma(shape=5.0, scale=mean_dur / 5.0), 10.0, 180.0))
            dur_min = round(dur_min, 2)

            comp_dt = req_dt + timedelta(minutes=resp_min + dur_min)

            writer.writerow([
                f"SRV-{idx:05d}",
                req_dt.isoformat(),
                urgency,
                stype,
                zone,
                chosen_unit["unit_id"],
                resp_min,
                dur_min,
                comp_dt.isoformat(),
                "COMPLETED",
            ])

    print(f"Generated synthetic dataset in {RAW_DIR}")


if __name__ == "__main__":
    main()
