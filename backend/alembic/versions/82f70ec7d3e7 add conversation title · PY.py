"""add conversation title

Revision ID: 82f70ec7d3e7
Revises: 4b88c676858b
Create Date: 2026-09-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "82f70ec7d3e7"
down_revision = "4b88c676858b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default is required here (not just the ORM-level
    # default in models.py) because this ALTER TABLE runs
    # against EXISTING rows — without a server-side default,
    # Postgres would reject the new NOT NULL column outright
    # on any table that already has conversations in it.
    op.add_column(
        "conversations",
        sa.Column(
            "title",
            sa.Text(),
            nullable=False,
            server_default="New Conversation",
        ),
    )

    # Drop the server_default after backfilling existing rows —
    # going forward we want the Python-side default in
    # models.py to be the single source of truth, not a
    # duplicate default living in the database schema.
    op.alter_column(
        "conversations",
        "title",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("conversations", "title")