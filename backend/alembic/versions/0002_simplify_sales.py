"""Keep users and business sales; remove shop and file metadata.

Users and sales values are preserved. Removed metadata cannot be reconstructed;
restore a pre-upgrade backup to recover the previous schema and its data.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_simplify_sales"
down_revision = "0001_phase1_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Detach every surviving reference before removing either parent table.
    op.drop_constraint(op.f("fk_users_shop_id_shops"), "users", type_="foreignkey")
    op.drop_constraint(op.f("fk_sales_shop_id_shops"), "sales", type_="foreignkey")
    op.drop_constraint(op.f("fk_sales_dataset_id_datasets"), "sales", type_="foreignkey")

    op.drop_index("ix_sales_dataset_id", table_name="sales")
    op.drop_index("ix_sales_product", table_name="sales")
    op.drop_index("ix_sales_shop_date_product", table_name="sales")
    op.drop_constraint(op.f("ck_sales_product_not_empty"), "sales", type_="check")
    op.drop_constraint(op.f("ck_sales_quantity_non_negative"), "sales", type_="check")

    # Rename in place, retaining IDs, dates, shop IDs, and fractional quantities.
    op.alter_column("sales", "product", new_column_name="sku_name")
    op.alter_column("sales", "quantity", new_column_name="num_units_sold")
    op.drop_column("sales", "dataset_id")
    op.drop_column("sales", "created_at")
    op.drop_column("sales", "updated_at")

    op.create_check_constraint(
        op.f("ck_sales_sku_name_not_empty"), "sales", "length(trim(sku_name)) > 0"
    )
    op.create_check_constraint(
        op.f("ck_sales_num_units_sold_non_negative"), "sales", "num_units_sold >= 0"
    )
    op.create_index("ix_sales_sku_name", "sales", ["sku_name"])
    op.create_index("ix_sales_shop_id_date", "sales", ["shop_id", "date"])

    # datasets still references shops/users, so remove it before shops.
    op.drop_table("datasets")
    op.drop_table("shops")
    sa.Enum(name="dataset_status_enum").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    raise RuntimeError(
        "This migration removes shop and file metadata irreversibly. "
        "Restore the pre-upgrade database backup to recover Phase 1."
    )
