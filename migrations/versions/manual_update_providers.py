"""update_providers_table

Revision ID: manual_update_providers
Revises: manual_add_messages
Create Date: 2024-05-22 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'manual_update_providers'
down_revision = 'manual_add_messages'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite ALTER TABLE support is limited.
    # We add columns one by one.
    with op.batch_alter_table('providers') as batch_op:
        batch_op.add_column(sa.Column('api_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('api_key_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('config', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('providers') as batch_op:
        batch_op.drop_column('api_url')
        batch_op.drop_column('api_key_name')
        batch_op.drop_column('config')
