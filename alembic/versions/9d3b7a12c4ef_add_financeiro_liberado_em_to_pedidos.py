"""add financeiro_liberado_em to pedidos

Revision ID: 9d3b7a12c4ef
Revises: c491056dde88
Create Date: 2026-03-16 19:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d3b7a12c4ef"
down_revision: Union[str, Sequence[str], None] = "c491056dde88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("pedidos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("financeiro_liberado_em", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("pedidos", schema=None) as batch_op:
        batch_op.drop_column("financeiro_liberado_em")
