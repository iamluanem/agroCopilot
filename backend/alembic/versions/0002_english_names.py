"""English column names for yields (bags of 60 kg per hectare)

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("crop_seasons", "expected_yield_sc_ha", new_column_name="expected_yield_bags_ha")
    op.alter_column("crop_seasons", "realized_yield_sc_ha", new_column_name="realized_yield_bags_ha")


def downgrade() -> None:
    op.alter_column("crop_seasons", "expected_yield_bags_ha", new_column_name="expected_yield_sc_ha")
    op.alter_column("crop_seasons", "realized_yield_bags_ha", new_column_name="realized_yield_sc_ha")
