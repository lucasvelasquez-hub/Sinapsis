"""Agregar ml_expected_min a decision.recommendation_candidates.

Predicción del modelo ML para cada candidato, guardada junto al tiempo esperado de la
recomendación (`expected_response_min`, hoy casi siempre la estimación por matriz × tráfico)
para poder evaluarlos por separado. No interviene en el orden del Top 3.

Revision ID: e3c8a7b5d1f2
Revises: d9b2e5a1c4f0
Create Date: 2026-11-25 18:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3c8a7b5d1f2"
down_revision: str | None = "d9b2e5a1c4f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recommendation_candidates",
        sa.Column("ml_expected_min", sa.Float(), nullable=True),
        schema="decision",
    )


def downgrade() -> None:
    op.drop_column("recommendation_candidates", "ml_expected_min", schema="decision")
