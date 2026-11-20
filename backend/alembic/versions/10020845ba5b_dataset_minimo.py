"""dataset minimo: raw.* con las columnas del dataset sintético mínimo

Revision ID: 10020845ba5b
Revises: 31e853de3d90
Create Date: 2026-11-20 00:03:30.952588

Los datos de raw/analytics se recrean con scripts/ingest_and_prepare.py, así que la migración
los vacía antes de cambiar la estructura. Sin CASCADE: si existen recomendaciones o decisiones
que referencian raw.services/raw.units, el DELETE falla y la migración aborta (protege la
auditoría). El downgrade restaura la estructura anterior, sin datos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "10020845ba5b"
down_revision: str | Sequence[str] | None = "31e853de3d90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _minutes_between(start: str, end: str) -> sa.Computed:
    return sa.Computed(
        f"(EXTRACT(EPOCH FROM ({end} - {start})) / 60.0)::double precision", persisted=True
    )


def _empty_raw_and_analytics() -> None:
    for table in (
        "analytics.prediction_results",
        "analytics.service_features",
        "analytics.unit_workload",
        "analytics.demand_aggregates",
        "raw.services",
        "raw.units",
        "raw.service_rules",
        "raw.response_targets",
    ):
        op.execute(f"DELETE FROM {table}")


def upgrade() -> None:
    _empty_raw_and_analytics()

    # response_targets: urgency_level + target_response_min
    op.drop_column("response_targets", "max_acceptable_min", schema="raw")
    op.drop_column("response_targets", "sla_label", schema="raw")
    op.drop_column("response_targets", "description", schema="raw")

    # service_rules: PK (service_type, unit_type) + eligible
    op.drop_index("ix_raw_service_rules_service_type", table_name="service_rules", schema="raw")
    op.drop_index("ix_raw_service_rules_unit_type", table_name="service_rules", schema="raw")
    op.drop_column("service_rules", "rule_id", schema="raw")  # arrastra service_rules_pkey
    op.drop_column("service_rules", "min_capacity", schema="raw")
    op.drop_column("service_rules", "notes", schema="raw")
    op.drop_column("service_rules", "compatible", schema="raw")
    op.drop_column("service_rules", "priority_rank", schema="raw")
    op.add_column(
        "service_rules", sa.Column("eligible", sa.Boolean(), nullable=False), schema="raw"
    )
    op.create_primary_key(
        "service_rules_pkey", "service_rules", ["service_type", "unit_type"], schema="raw"
    )

    # services: timestamps de origen + tiempos derivados generados por Postgres
    op.drop_column("services", "completion_datetime", schema="raw")
    op.drop_column("services", "response_time_min", schema="raw")
    op.drop_column("services", "service_duration_min", schema="raw")
    for col in ("assignment_datetime", "arrival_datetime", "closure_datetime"):
        op.add_column("services", sa.Column(col, sa.DateTime(), nullable=True), schema="raw")
    op.add_column(
        "services",
        sa.Column(
            "response_time_min",
            sa.Float(),
            _minutes_between("request_datetime", "arrival_datetime"),
            nullable=True,
        ),
        schema="raw",
    )
    op.add_column(
        "services",
        sa.Column(
            "service_duration_min",
            sa.Float(),
            _minutes_between("arrival_datetime", "closure_datetime"),
            nullable=True,
        ),
        schema="raw",
    )
    op.add_column(
        "services",
        sa.Column(
            "occupation_min",
            sa.Float(),
            _minutes_between("assignment_datetime", "closure_datetime"),
            nullable=True,
        ),
        schema="raw",
    )
    op.drop_constraint("ck_services_urgency", "services", schema="raw", type_="check")
    op.create_check_constraint(
        "ck_services_urgency",
        "services",
        "urgency_level IN ('CRITICA', 'ALTA', 'MEDIA', 'BAJA')",
        schema="raw",
    )

    # units: base_id + cost_per_km; sin unit_code ni base_zone_id
    op.drop_index("ix_raw_units_base_zone_id", table_name="units", schema="raw")
    op.drop_constraint("units_unit_code_key", "units", schema="raw", type_="unique")
    op.drop_column("units", "base_zone_id", schema="raw")
    op.drop_column("units", "unit_code", schema="raw")
    op.add_column("units", sa.Column("base_id", sa.String(length=16), nullable=False), schema="raw")
    op.add_column("units", sa.Column("cost_per_km", sa.Float(), nullable=True), schema="raw")
    op.create_index("ix_raw_units_base_id", "units", ["base_id"], unique=False, schema="raw")


def downgrade() -> None:
    _empty_raw_and_analytics()

    op.drop_index("ix_raw_units_base_id", table_name="units", schema="raw")
    op.drop_column("units", "cost_per_km", schema="raw")
    op.drop_column("units", "base_id", schema="raw")
    op.add_column(
        "units", sa.Column("unit_code", sa.VARCHAR(length=24), nullable=False), schema="raw"
    )
    op.add_column(
        "units", sa.Column("base_zone_id", sa.VARCHAR(length=16), nullable=False), schema="raw"
    )
    op.create_unique_constraint("units_unit_code_key", "units", ["unit_code"], schema="raw")
    op.create_index("ix_raw_units_base_zone_id", "units", ["base_zone_id"], schema="raw")

    op.drop_constraint("ck_services_urgency", "services", schema="raw", type_="check")
    op.create_check_constraint(
        "ck_services_urgency",
        "services",
        "urgency_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')",
        schema="raw",
    )
    for col in (
        "occupation_min",
        "service_duration_min",
        "response_time_min",
        "closure_datetime",
        "arrival_datetime",
        "assignment_datetime",
    ):
        op.drop_column("services", col, schema="raw")
    op.add_column(
        "services", sa.Column("response_time_min", sa.Float(), nullable=True), schema="raw"
    )
    op.add_column(
        "services", sa.Column("service_duration_min", sa.Float(), nullable=True), schema="raw"
    )
    op.add_column(
        "services",
        sa.Column("completion_datetime", postgresql.TIMESTAMP(), nullable=True),
        schema="raw",
    )

    op.drop_constraint("service_rules_pkey", "service_rules", schema="raw", type_="primary")
    op.drop_column("service_rules", "eligible", schema="raw")
    op.add_column(
        "service_rules", sa.Column("rule_id", sa.VARCHAR(length=16), nullable=False), schema="raw"
    )
    op.add_column(
        "service_rules", sa.Column("compatible", sa.BOOLEAN(), nullable=False), schema="raw"
    )
    op.add_column(
        "service_rules", sa.Column("priority_rank", sa.INTEGER(), nullable=False), schema="raw"
    )
    op.add_column(
        "service_rules", sa.Column("min_capacity", sa.INTEGER(), nullable=False), schema="raw"
    )
    op.add_column("service_rules", sa.Column("notes", sa.TEXT(), nullable=False), schema="raw")
    op.create_primary_key("service_rules_pkey", "service_rules", ["rule_id"], schema="raw")
    op.create_index(
        "ix_raw_service_rules_service_type", "service_rules", ["service_type"], schema="raw"
    )
    op.create_index("ix_raw_service_rules_unit_type", "service_rules", ["unit_type"], schema="raw")

    op.add_column(
        "response_targets",
        sa.Column("max_acceptable_min", sa.INTEGER(), nullable=False),
        schema="raw",
    )
    op.add_column(
        "response_targets",
        sa.Column("sla_label", sa.VARCHAR(length=32), nullable=False),
        schema="raw",
    )
    op.add_column(
        "response_targets", sa.Column("description", sa.TEXT(), nullable=False), schema="raw"
    )
