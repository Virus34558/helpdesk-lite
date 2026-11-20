"""version de bloqueo optimista en incidencias

Revision ID: e7b2d94c8a13
Revises: d1a4e8c37f65
Create Date: 2026-11-20 12:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7b2d94c8a13"
down_revision: str | Sequence[str] | None = "d1a4e8c37f65"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "incidencias",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("incidencias", "version")
