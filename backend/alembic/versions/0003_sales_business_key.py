"""Enforce one daily sales record per shop and SKU, without altering data."""
from alembic import op

revision = "0003_sales_business_key"
down_revision = "0002_simplify_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Prevent concurrent writes between the duplicate check and constraint creation.
    # ALTER TABLE ADD UNIQUE also needs this lock; hold it through the transaction.
    op.execute("LOCK TABLE sales IN ACCESS EXCLUSIVE MODE")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM sales
                GROUP BY shop_id, date, sku_name HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION 'Cannot enforce sales uniqueness: duplicate (shop_id, date, sku_name) records exist. No sales data was changed.'
                    USING HINT = 'Inspect duplicates with SELECT shop_id, date, sku_name, count(*) FROM sales GROUP BY shop_id, date, sku_name HAVING count(*) > 1; resolve them explicitly before retrying.';
            END IF;
        END $$
    """)
    op.create_unique_constraint(
        "uq_sales_shop_id_date_sku_name", "sales", ["shop_id", "date", "sku_name"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_sales_shop_id_date_sku_name", "sales", type_="unique")
