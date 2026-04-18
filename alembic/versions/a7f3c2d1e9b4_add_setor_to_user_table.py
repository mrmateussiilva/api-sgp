"""add setor to user table

Revision ID: a7f3c2d1e9b4
Revises: 9d3b7a12c4ef
Create Date: 2026-04-18 19:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7f3c2d1e9b4"
down_revision: Union[str, Sequence[str], None] = "9d3b7a12c4ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("setor", sa.String(50), nullable=True, server_default="geral"))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("setor")
