"""plantillas de respuesta

Revision ID: d1a4e8c37f65
Revises: c9f2a7d61e58
Create Date: 2026-11-20 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1a4e8c37f65"
down_revision: str | Sequence[str] | None = "c9f2a7d61e58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "macros",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("es_interna", sa.Boolean(), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_macros_nombre", "macros", ["nombre"], unique=True)
    op.create_index("ix_macros_activa", "macros", ["activa"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_macros_activa", table_name="macros")
    op.drop_index("ix_macros_nombre", table_name="macros")
    op.drop_table("macros")
