"""add_messages_table

Revision ID: manual_add_messages
Revises: 77e37576d65f
Create Date: 2024-05-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'manual_add_messages'
down_revision = '77e37576d65f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('conversation_id', sa.Integer(), sa.ForeignKey('conversations.id'), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('tool_calls', sa.JSON(), nullable=True),
        sa.Column('tool_outputs', sa.JSON(), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index(op.f('ix_messages_id'), 'messages', ['id'], unique=False)
    op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'], unique=False)


def downgrade():
    op.drop_table('messages')
