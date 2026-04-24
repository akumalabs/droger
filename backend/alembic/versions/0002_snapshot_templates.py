"""add snapshot templates

Revision ID: 0002_snapshot_templates
Revises: 0001_initial_schema
Create Date: 2026-04-25 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002_snapshot_templates"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "snapshot_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("current_image_id", sa.BigInteger(), nullable=False),
        sa.Column("source_droplet_id", sa.BigInteger(), nullable=True),
        sa.Column("snapshot_name", sa.String(length=255), nullable=True),
        sa.Column("current_token_id", sa.String(length=64), nullable=False),
        sa.Column("current_do_uuid", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_snapshot_templates_template_id"), "snapshot_templates", ["template_id"], unique=True)
    op.create_index(op.f("ix_snapshot_templates_user_id"), "snapshot_templates", ["user_id"], unique=False)
    op.create_index(op.f("ix_snapshot_templates_current_token_id"), "snapshot_templates", ["current_token_id"], unique=False)
    op.create_index(op.f("ix_snapshot_templates_created_at"), "snapshot_templates", ["created_at"], unique=False)
    op.create_index(op.f("ix_snapshot_templates_updated_at"), "snapshot_templates", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_snapshot_templates_updated_at"), table_name="snapshot_templates")
    op.drop_index(op.f("ix_snapshot_templates_created_at"), table_name="snapshot_templates")
    op.drop_index(op.f("ix_snapshot_templates_current_token_id"), table_name="snapshot_templates")
    op.drop_index(op.f("ix_snapshot_templates_user_id"), table_name="snapshot_templates")
    op.drop_index(op.f("ix_snapshot_templates_template_id"), table_name="snapshot_templates")
    op.drop_table("snapshot_templates")
