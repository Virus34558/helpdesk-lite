"""observadores en copia (CC) por incidencia

Revision ID: c9f2a7d61e58
Revises: b3e5c7a91d42
Create Date: 2026-11-20 11:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9f2a7d61e58"
down_revision: str | Sequence[str] | None = "b3e5c7a91d42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "observadores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incidencia_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["incidencia_id"], ["incidencias.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "incidencia_id", "email", name="uq_observador_incidencia_email"
        ),
    )
    op.create_index(
        "ix_observadores_incidencia_id",
        "observadores",
        ["incidencia_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_observadores_incidencia_id", table_name="observadores")
    op.drop_table("observadores")
