"""Record the original Phase 1 schema, previously shipped without revisions.

Existing matching databases must stamp this revision before upgrading.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_phase1_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('shops',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_shops'))
    )
    op.create_index(op.f('ix_shops_id'), 'shops', ['id'], unique=False)
    op.create_index(op.f('ix_shops_name'), 'shops', ['name'], unique=True)
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['shop_id'], ['shops.id'], name=op.f('fk_users_shop_id_shops'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_shop_id'), 'users', ['shop_id'], unique=False)
    op.create_table('datasets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('file_type', sa.String(length=20), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('status', sa.Enum('UPLOADED', 'PROCESSING', 'COMPLETED', 'FAILED', name='dataset_status_enum'), server_default='UPLOADED', nullable=False),
        sa.Column('rows_processed', sa.Integer(), server_default='0', nullable=False),
        sa.Column('date_from', sa.Date(), nullable=True),
        sa.Column('date_to', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['shop_id'], ['shops.id'], name=op.f('fk_datasets_shop_id_shops'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('fk_datasets_uploaded_by_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_datasets'))
    )
    op.create_index(op.f('ix_datasets_file_hash'), 'datasets', ['file_hash'], unique=False)
    op.create_index(op.f('ix_datasets_id'), 'datasets', ['id'], unique=False)
    op.create_index(op.f('ix_datasets_shop_id'), 'datasets', ['shop_id'], unique=False)
    op.create_index('ix_datasets_shop_id_file_hash', 'datasets', ['shop_id', 'file_hash'], unique=False)
    op.create_index(op.f('ix_datasets_status'), 'datasets', ['status'], unique=False)
    op.create_index(op.f('ix_datasets_uploaded_by'), 'datasets', ['uploaded_by'], unique=False)
    op.create_table('sales',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('product', sa.String(length=255), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('length(trim(product)) > 0', name=op.f('ck_sales_product_not_empty')),
        sa.CheckConstraint('quantity >= 0', name=op.f('ck_sales_quantity_non_negative')),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], name=op.f('fk_sales_dataset_id_datasets'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shop_id'], ['shops.id'], name=op.f('fk_sales_shop_id_shops'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_sales'))
    )
    op.create_index(op.f('ix_sales_dataset_id'), 'sales', ['dataset_id'], unique=False)
    op.create_index(op.f('ix_sales_date'), 'sales', ['date'], unique=False)
    op.create_index(op.f('ix_sales_id'), 'sales', ['id'], unique=False)
    op.create_index(op.f('ix_sales_product'), 'sales', ['product'], unique=False)
    op.create_index('ix_sales_shop_date_product', 'sales', ['shop_id', 'date', 'product'], unique=False)
    op.create_index(op.f('ix_sales_shop_id'), 'sales', ['shop_id'], unique=False)


def downgrade() -> None:
    op.drop_table("sales")
    op.drop_table("datasets")
    op.drop_table("users")
    op.drop_table("shops")
    sa.Enum(name="dataset_status_enum").drop(op.get_bind(), checkfirst=True)
