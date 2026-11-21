"""Agregar distance_km a decision.recommendation_candidates.

Revision ID: d9b2e5a1c4f0
Revises: c7a1f4d9e2b3
Create Date: 2026-11-21 12:38:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9b2e5a1c4f0"
down_revision: str | None = "c7a1f4d9e2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recommendation_candidates",
        sa.Column("distance_km", sa.Float(), nullable=True),
        schema="decision",
    )


def downgrade() -> None:
    op.drop_column("recommendation_candidates", "distance_km", schema="decision")
