"""Adaptar esquema al dataset real de Grupo EMI (zonas, tiempos, tráfico, costos y reglas).

Revision ID: c7a1f4d9e2b3
Revises: fb8e822f8f09
Create Date: 2026-11-21 10:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7a1f4d9e2b3"
down_revision: str | None = "fb8e822f8f09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bases",
        sa.Column("base_id", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("municipality", sa.String(length=64), nullable=False),
        sa.Column("zone_id", sa.String(length=32), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("base_id"),
        schema="raw",
    )
    op.create_index(op.f("ix_raw_bases_zone_id"), "bases", ["zone_id"], unique=False, schema="raw")

    op.create_table(
        "zones",
        sa.Column("zone_id", sa.String(length=32), nullable=False),
        sa.Column("municipality", sa.String(length=64), nullable=False),
        sa.Column("comuna", sa.String(length=64), nullable=False),
        sa.Column("lat_centroid", sa.Float(), nullable=False),
        sa.Column("lon_centroid", sa.Float(), nullable=False),
        sa.Column("relative_demand", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("zone_id"),
        schema="raw",
    )
    op.create_index(
        op.f("ix_raw_zones_relative_demand"),
        "zones",
        ["relative_demand"],
        unique=False,
        schema="raw",
    )

    op.create_table(
        "zone_travel_times",
        sa.Column("origin_zone_id", sa.String(length=32), nullable=False),
        sa.Column("destination_zone_id", sa.String(length=32), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("valley_time_min", sa.Float(), nullable=False),
        sa.Column("peak_time_min", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("origin_zone_id", "destination_zone_id"),
        schema="raw",
    )

    op.create_table(
        "traffic_factors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("day_type", sa.String(length=24), nullable=False),
        sa.Column("hour_start", sa.Integer(), nullable=False),
        sa.Column("hour_end", sa.Integer(), nullable=False),
        sa.Column("factor", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="raw",
    )
    op.create_index(
        op.f("ix_raw_traffic_factors_day_type"),
        "traffic_factors",
        ["day_type"],
        unique=False,
        schema="raw",
    )

    op.create_table(
        "care_centers",
        sa.Column("center_id", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("zone_id", sa.String(length=32), nullable=False),
        sa.Column("complexity_level", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("center_id"),
        schema="raw",
    )
    op.create_index(
        op.f("ix_raw_care_centers_zone_id"),
        "care_centers",
        ["zone_id"],
        unique=False,
        schema="raw",
    )

    op.add_column(
        "response_targets",
        sa.Column("description", sa.String(length=64), server_default="", nullable=False),
        schema="raw",
    )
    op.add_column(
        "response_targets",
        sa.Column("manchester_scale", sa.String(length=16), server_default="", nullable=False),
        schema="raw",
    )

    op.execute("TRUNCATE TABLE raw.service_rules")
    op.drop_constraint("service_rules_pkey", "service_rules", schema="raw", type_="primary")
    op.alter_column(
        "service_rules",
        "service_type",
        new_column_name="urgency_level",
        type_=sa.String(length=16),
        existing_type=sa.String(length=32),
        existing_nullable=False,
        schema="raw",
    )
    op.add_column(
        "service_rules",
        sa.Column(
            "compatibility_level",
            sa.String(length=24),
            server_default="PERMITIDA",
            nullable=False,
        ),
        schema="raw",
    )
    op.add_column(
        "service_rules",
        sa.Column("compatibility_rank", sa.Integer(), server_default="2", nullable=False),
        schema="raw",
    )
    op.create_primary_key(
        "service_rules_pkey", "service_rules", ["urgency_level", "unit_type"], schema="raw"
    )

    op.add_column("units", sa.Column("cost_per_hour", sa.Float(), nullable=True), schema="raw")
    op.add_column(
        "units", sa.Column("observation", sa.String(length=256), nullable=True), schema="raw"
    )
    op.execute(
        "ALTER TABLE raw.units ADD CONSTRAINT fk_raw_units_base_id "
        "FOREIGN KEY (base_id) REFERENCES raw.bases(base_id) NOT VALID"
    )

    op.drop_constraint("ck_services_urgency", "services", schema="raw", type_="check")
    op.execute(
        "ALTER TABLE raw.services ADD CONSTRAINT ck_services_urgency "
        "CHECK (urgency_level IN ('01', '02', '07', '03', '06')) NOT VALID"
    )
    op.alter_column(
        "services",
        "service_type",
        type_=sa.String(length=128),
        existing_type=sa.String(length=32),
        existing_nullable=False,
        schema="raw",
    )
    op.alter_column(
        "services",
        "zone_id",
        type_=sa.String(length=32),
        existing_type=sa.String(length=16),
        existing_nullable=False,
        schema="raw",
    )
    op.add_column(
        "services", sa.Column("dispatch_datetime", sa.DateTime(), nullable=True), schema="raw"
    )
    op.add_column(
        "services",
        sa.Column("manchester_scale", sa.String(length=16), nullable=True),
        schema="raw",
    )
    op.add_column(
        "services", sa.Column("discriminator", sa.String(length=128), nullable=True), schema="raw"
    )
    op.add_column(
        "services", sa.Column("channel", sa.String(length=24), nullable=True), schema="raw"
    )
    op.add_column("services", sa.Column("lat_approx", sa.Float(), nullable=True), schema="raw")
    op.add_column("services", sa.Column("lon_approx", sa.Float(), nullable=True), schema="raw")
    op.add_column(
        "services", sa.Column("origin_zone_id", sa.String(length=32), nullable=True), schema="raw"
    )
    op.add_column("services", sa.Column("distance_km", sa.Float(), nullable=True), schema="raw")
    op.add_column(
        "services", sa.Column("reported_response_min", sa.Float(), nullable=True), schema="raw"
    )
    op.add_column(
        "services", sa.Column("required_transfer", sa.Boolean(), nullable=True), schema="raw"
    )
    op.add_column(
        "services",
        sa.Column("destination_center", sa.String(length=128), nullable=True),
        schema="raw",
    )
    op.add_column(
        "services", sa.Column("closure_state", sa.String(length=40), nullable=True), schema="raw"
    )
    op.add_column(
        "services",
        sa.Column(
            "classifications_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        schema="raw",
    )
    op.add_column(
        "services",
        sa.Column(
            "assigned_units_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        schema="raw",
    )

    op.add_column(
        "recommendation_candidates",
        sa.Column("cost_penalty", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        schema="decision",
    )
    op.add_column(
        "recommendation_candidates",
        sa.Column("coverage_penalty", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        schema="decision",
    )
    op.add_column(
        "recommendation_candidates",
        sa.Column("estimated_travel_min", sa.Float(), nullable=True),
        schema="decision",
    )
    op.add_column(
        "recommendation_candidates",
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        schema="decision",
    )
    op.add_column(
        "recommendation_candidates",
        sa.Column("recommended_role", sa.String(length=40), nullable=True),
        schema="decision",
    )
    op.add_column(
        "recommendation_candidates",
        sa.Column("paired_unit_id", sa.String(length=16), nullable=True),
        schema="decision",
    )


def downgrade() -> None:
    op.drop_column("recommendation_candidates", "paired_unit_id", schema="decision")
    op.drop_column("recommendation_candidates", "recommended_role", schema="decision")
    op.drop_column("recommendation_candidates", "estimated_cost", schema="decision")
    op.drop_column("recommendation_candidates", "estimated_travel_min", schema="decision")
    op.drop_column("recommendation_candidates", "coverage_penalty", schema="decision")
    op.drop_column("recommendation_candidates", "cost_penalty", schema="decision")

    for col in (
        "assigned_units_json",
        "classifications_json",
        "closure_state",
        "destination_center",
        "required_transfer",
        "reported_response_min",
        "distance_km",
        "origin_zone_id",
        "lon_approx",
        "lat_approx",
        "channel",
        "discriminator",
        "manchester_scale",
        "dispatch_datetime",
    ):
        op.drop_column("services", col, schema="raw")

    op.drop_constraint("ck_services_urgency", "services", schema="raw", type_="check")
    op.execute(
        "ALTER TABLE raw.services ADD CONSTRAINT ck_services_urgency "
        "CHECK (urgency_level IN ('CRITICA', 'ALTA', 'MEDIA', 'BAJA')) NOT VALID"
    )

    op.drop_constraint("fk_raw_units_base_id", "units", schema="raw", type_="foreignkey")
    op.drop_column("units", "observation", schema="raw")
    op.drop_column("units", "cost_per_hour", schema="raw")

    op.drop_constraint("service_rules_pkey", "service_rules", schema="raw", type_="primary")
    op.drop_column("service_rules", "compatibility_rank", schema="raw")
    op.drop_column("service_rules", "compatibility_level", schema="raw")
    op.alter_column(
        "service_rules",
        "urgency_level",
        new_column_name="service_type",
        type_=sa.String(length=32),
        existing_type=sa.String(length=16),
        existing_nullable=False,
        schema="raw",
    )
    op.create_primary_key(
        "service_rules_pkey", "service_rules", ["service_type", "unit_type"], schema="raw"
    )

    op.drop_column("response_targets", "manchester_scale", schema="raw")
    op.drop_column("response_targets", "description", schema="raw")

    op.drop_index(op.f("ix_raw_care_centers_zone_id"), table_name="care_centers", schema="raw")
    op.drop_table("care_centers", schema="raw")
    op.drop_index(op.f("ix_raw_traffic_factors_day_type"), table_name="traffic_factors", schema="raw")
    op.drop_table("traffic_factors", schema="raw")
    op.drop_table("zone_travel_times", schema="raw")
    op.drop_index(op.f("ix_raw_zones_relative_demand"), table_name="zones", schema="raw")
    op.drop_table("zones", schema="raw")
    op.drop_index(op.f("ix_raw_bases_zone_id"), table_name="bases", schema="raw")
    op.drop_table("bases", schema="raw")
