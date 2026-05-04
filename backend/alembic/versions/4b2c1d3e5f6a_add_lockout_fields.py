"""add lockout fields

Revision ID: 4b2c1d3e5f6a
Revises: 309cfaddb5d0
Create Date: 2026-05-04 14:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4b2c1d3e5f6a'
down_revision = '309cfaddb5d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns with nullable=True first, then set default for existing rows if needed
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('users', sa.Column('lockout_until', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'lockout_until')
    op.drop_column('users', 'failed_login_attempts')
