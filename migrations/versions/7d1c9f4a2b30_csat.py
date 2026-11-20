"""encuesta CSAT en incidencias

Revision ID: 7d1c9f4a2b30
Revises: 5c2debf054a0
Create Date: 2026-11-20 10:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d1c9f4a2b30"
down_revision: str | Sequence[str] | None = "5c2debf054a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("incidencias", sa.Column("csat_puntuacion", sa.Integer(), nullable=True))
    op.add_column("incidencias", sa.Column("csat_comentario", sa.Text(), nullable=True))
    op.add_column("incidencias", sa.Column("csat_en", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("incidencias", "csat_en")
    op.drop_column("incidencias", "csat_comentario")
    op.drop_column("incidencias", "csat_puntuacion")
