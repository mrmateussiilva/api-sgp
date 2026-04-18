"""add password_plain to user table

Revision ID: b8e4d3f2a1c5
Revises: a7f3c2d1e9b4
Create Date: 2026-04-18 20:17:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8e4d3f2a1c5"
down_revision: Union[str, Sequence[str], None] = "a7f3c2d1e9b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("password_plain", sa.String(200), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("password_plain")
