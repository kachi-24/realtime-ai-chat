"""add google login

Revision ID: 04a8cd0a1293
Revises: ad2a75a18e61
"""
from alembic import op
import sqlalchemy as sa

revision = "04a8cd0a1293"
down_revision = "ad2a75a18e61"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    # Fails if any Google-only users (NULL password_hash) still exist.
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=False)
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    op.drop_column("users", "google_sub")