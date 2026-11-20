"""add integrity constraints

FKs between decision/raw tables, one decision per service, closed vocabularies
(CHECK) and weight bounds. Seeds the default scoring config so it is never created
lazily inside a request.

Note: with these FKs, re-running scripts/ingest_and_prepare.py on a database that
already holds decisions fails on purpose (audit rows must not be orphaned).

Revision ID: 545b0996db2b
Revises: faa75e1c0208
Create Date: 2026-11-19 19:08:19.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "545b0996db2b"
down_revision: str | Sequence[str] | None = "faa75e1c0208"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (name, source_table, source_schema, column, referent_table, referent_schema, referent_col)
FOREIGN_KEYS = [
    ("fk_services_assigned_unit_id_units", "services", "raw", "assigned_unit_id", "units", "raw", "unit_id"),
    ("fk_recommendations_service_id_services", "recommendations", "decision", "service_id", "services", "raw", "service_id"),
    ("fk_recommendation_candidates_unit_id_units", "recommendation_candidates", "decision", "unit_id", "units", "raw", "unit_id"),
    ("fk_dispatch_decisions_service_id_services", "dispatch_decisions", "decision", "service_id", "services", "raw", "service_id"),
    ("fk_dispatch_decisions_recommendation_id_recommendations", "dispatch_decisions", "decision", "recommendation_id", "recommendations", "decision", "recommendation_id"),
    ("fk_dispatch_decisions_recommended_unit_id_units", "dispatch_decisions", "decision", "recommended_unit_id", "units", "raw", "unit_id"),
    ("fk_dispatch_decisions_assigned_unit_id_units", "dispatch_decisions", "decision", "assigned_unit_id", "units", "raw", "unit_id"),
]

# (name, table, schema, condition)
CHECKS = [
    ("ck_services_status", "services", "raw", "status IN ('PENDING', 'DISPATCHED', 'REJECTED', 'COMPLETED')"),
    ("ck_services_urgency", "services", "raw", "urgency_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')"),
    ("ck_recommendations_status", "recommendations", "decision", "status IN ('GENERATED', 'NO_ELIGIBLE_UNITS')"),
    ("ck_decisions_accepted_has_unit", "dispatch_decisions", "decision", "NOT accepted OR assigned_unit_id IS NOT NULL"),
    ("ck_decisions_rejection_has_reason", "dispatch_decisions", "decision", "accepted OR assigned_unit_id IS NOT NULL OR rejection_reason IS NOT NULL"),
    (
        "ck_scoring_weights_unit_interval",
        "scoring_config",
        "core",
        "weight_time BETWEEN 0 AND 1 AND weight_workload BETWEEN 0 AND 1"
        " AND weight_cost BETWEEN 0 AND 1 AND weight_coverage BETWEEN 0 AND 1",
    ),
]


def upgrade() -> None:
    op.drop_index("ix_decision_dispatch_decisions_service_id", table_name="dispatch_decisions", schema="decision")
    op.create_index("ix_decision_dispatch_decisions_service_id", "dispatch_decisions", ["service_id"], unique=True, schema="decision")
    for name, src, src_schema, col, ref, ref_schema, ref_col in FOREIGN_KEYS:
        op.create_foreign_key(name, src, ref, [col], [ref_col], source_schema=src_schema, referent_schema=ref_schema)
    for name, table, schema, condition in CHECKS:
        op.create_check_constraint(name, table, condition, schema=schema)
    op.execute(
        "INSERT INTO core.scoring_config (config_id, weight_time, weight_workload, weight_cost,"
        " weight_coverage, cost_enabled, coverage_enabled, updated_at)"
        " VALUES ('default', 0.80, 0.20, 0.0, 0.0, false, false, (now() AT TIME ZONE 'utc'))"
        " ON CONFLICT (config_id) DO NOTHING"
    )


def downgrade() -> None:
    # The seeded scoring config is kept: it may have been edited since (audited data).
    for name, table, schema, _ in reversed(CHECKS):
        op.drop_constraint(name, table, schema=schema, type_="check")
    for name, src, src_schema, *_ in reversed(FOREIGN_KEYS):
        op.drop_constraint(name, src, schema=src_schema, type_="foreignkey")
    op.drop_index("ix_decision_dispatch_decisions_service_id", table_name="dispatch_decisions", schema="decision")
    op.create_index("ix_decision_dispatch_decisions_service_id", "dispatch_decisions", ["service_id"], unique=False, schema="decision")
