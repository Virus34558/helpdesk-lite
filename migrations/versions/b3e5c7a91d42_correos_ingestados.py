"""tabla de correos ingestados (antiduplicados)

Revision ID: b3e5c7a91d42
Revises: 7d1c9f4a2b30
Create Date: 2026-11-20 11:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3e5c7a91d42"
down_revision: str | Sequence[str] | None = "7d1c9f4a2b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "correos_ingestados",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mensaje_id", sa.String(length=255), nullable=False),
        sa.Column("incidencia_id", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["incidencia_id"], ["incidencias.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_correos_ingestados_mensaje_id",
        "correos_ingestados",
        ["mensaje_id"],
        unique=True,
    )
    op.create_index(
        "ix_correos_ingestados_incidencia_id",
        "correos_ingestados",
        ["incidencia_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_correos_ingestados_incidencia_id", table_name="correos_ingestados")
    op.drop_index("ix_correos_ingestados_mensaje_id", table_name="correos_ingestados")
    op.drop_table("correos_ingestados")
