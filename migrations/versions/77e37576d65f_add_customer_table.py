"""add customer table

Revision ID: 77e37576d65f
Revises: fc71da265a58
Create Date: 2026-08-02 11:24:35.334748

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77e37576d65f'
down_revision: Union[str, Sequence[str], None] = 'fc71da265a58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('customers',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.String(length=1000), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=255), nullable=True),
    sa.Column('address', sa.String(length=255), nullable=True),
    sa.Column('city', sa.String(length=255), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customers_id'), 'customers', ['id'], unique=False)
    op.create_index('ix_customers_is_active_id', 'customers', ['is_active', 'id'], unique=False)
    op.create_index(op.f('ix_customers_name'), 'customers', ['name'], unique=False)
    op.create_table('payments',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('invoice_id', sa.Integer(), nullable=False),
    sa.Column('payment_method', sa.String(length=50), nullable=False),
    sa.Column('payment_date', sa.DateTime(timezone=True), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default='CURRENT_TIMESTAMP', nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default='CURRENT_TIMESTAMP', nullable=False),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payments_id'), 'payments', ['id'], unique=False)
    op.create_index(op.f('ix_payments_invoice_id'), 'payments', ['invoice_id'], unique=False)
    
    with op.batch_alter_table('books', schema=None) as batch_op:
        batch_op.alter_column('id', existing_type=sa.INTEGER(), nullable=False, autoincrement=True)
        batch_op.create_index(op.f('ix_books_id'), ['id'], unique=False)
        batch_op.create_index('ix_books_is_active_id', ['is_active', 'id'], unique=False)
        batch_op.create_index(op.f('ix_books_judul'), ['judul'], unique=False)
        batch_op.create_index(op.f('ix_books_name'), ['name'], unique=False)

    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('model_id')
        batch_op.drop_column('provider_id')

    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.create_index(op.f('ix_invoices_order_id'), ['order_id'], unique=False)
        batch_op.create_foreign_key(None, 'orders', ['order_id'], ['id'])

    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.alter_column('id', existing_type=sa.INTEGER(), nullable=False, autoincrement=True)
        batch_op.create_index(op.f('ix_order_items_id'), ['id'], unique=False)
        batch_op.create_index(op.f('ix_order_items_order_id'), ['order_id'], unique=False)
        batch_op.create_index(op.f('ix_order_items_product_id'), ['product_id'], unique=False)

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('status', existing_type=sa.VARCHAR(length=50), nullable=False, existing_server_default=sa.text('("pending")'))
        batch_op.create_index(op.f('ix_orders_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key(None, 'users', ['user_id'], ['id'])

    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.alter_column('description', existing_type=sa.TEXT(), type_=sa.String(), existing_nullable=True)

    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.alter_column('name', existing_type=sa.VARCHAR(length=50), type_=sa.String(length=255), existing_nullable=False)
        batch_op.alter_column('is_active', existing_type=sa.BOOLEAN(), nullable=False)
        batch_op.drop_index(op.f('ix_roles_id'))
        batch_op.create_index(op.f('ix_roles_id'), ['id'], unique=False)
        batch_op.drop_index(op.f('ix_roles_name'))
        batch_op.create_index(op.f('ix_roles_name'), ['name'], unique=False)
        batch_op.drop_column('is_deleted')
        batch_op.drop_column('deleted_at')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('created_at', existing_type=sa.DATETIME(), nullable=True, existing_server_default=sa.text('(CURRENT_TIMESTAMP)'))
        batch_op.alter_column('updated_at', existing_type=sa.DATETIME(), nullable=True, existing_server_default=sa.text('(CURRENT_TIMESTAMP)'))
        batch_op.drop_index(op.f('ix_users_id'))
        batch_op.create_index(op.f('ix_users_id'), ['id'], unique=False)
