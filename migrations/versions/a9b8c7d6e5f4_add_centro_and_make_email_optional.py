"""Add centro field and make email optional in User model

Revision ID: a9b8c7d6e5f4
Revises: d1733d27f14f
Create Date: 2025-11-28 17:26:46.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9b8c7d6e5f4'
down_revision = 'd1733d27f14f'
branch_labels = None
depends_on = None


def upgrade():
    # Add centro column
    op.add_column('users', sa.Column('centro', sa.String(length=200), nullable=True))

    # Make email nullable
    op.alter_column('users', 'email',
                    existing_type=sa.String(length=120),
                    nullable=True)


def downgrade():
    # Make email NOT nullable again
    op.alter_column('users', 'email',
                    existing_type=sa.String(length=120),
                    nullable=False)

    # Drop centro column
    op.drop_column('users', 'centro')
