"""remove snapshot template feature tables

Revision ID: 0004_remove_templates_feature
Revises: 0003_template_account_states
Create Date: 2026-04-25 00:00:02.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004_remove_templates_feature"
down_revision: Union[str, None] = "0003_template_account_states"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {idx["name"] for idx in inspector.get_indexes(table_name)}
    if index_name in existing:
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    _drop_index_if_exists("snapshot_template_account_states", op.f("ix_snapshot_template_account_states_updated_at"))
    _drop_index_if_exists("snapshot_template_account_states", op.f("ix_snapshot_template_account_states_created_at"))
    _drop_index_if_exists("snapshot_template_account_states", op.f("ix_snapshot_template_account_states_token_id"))
    _drop_index_if_exists("snapshot_template_account_states", op.f("ix_snapshot_template_account_states_user_id"))
    _drop_index_if_exists("snapshot_template_account_states", op.f("ix_snapshot_template_account_states_template_id"))
    op.drop_table("snapshot_template_account_states")

    _drop_index_if_exists("snapshot_templates", op.f("ix_snapshot_templates_updated_at"))
    _drop_index_if_exists("snapshot_templates", op.f("ix_snapshot_templates_created_at"))
    _drop_index_if_exists("snapshot_templates", op.f("ix_snapshot_templates_current_token_id"))
    _drop_index_if_exists("snapshot_templates", op.f("ix_snapshot_templates_owner_token_id"))
    _drop_index_if_exists("snapshot_templates", op.f("ix_snapshot_templates_user_id"))
    _drop_index_if_exists("snapshot_templates", op.f("ix_snapshot_templates_template_id"))
    op.drop_table("snapshot_templates")


def downgrade() -> None:
    op.create_table(
        "snapshot_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("current_image_id", sa.BigInteger(), nullable=False),
        sa.Column("source_droplet_id", sa.BigInteger(), nullable=True),
        sa.Column("snapshot_name", sa.String(length=255), nullable=True),
        sa.Column("owner_token_id", sa.String(length=64), nullable=False),
        sa.Column("owner_account_uuid", sa.String(length=120), nullable=True),
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
    op.create_index(op.f("ix_snapshot_templates_owner_token_id"), "snapshot_templates", ["owner_token_id"], unique=False)
    op.create_index(op.f("ix_snapshot_templates_created_at"), "snapshot_templates", ["created_at"], unique=False)
    op.create_index(op.f("ix_snapshot_templates_updated_at"), "snapshot_templates", ["updated_at"], unique=False)

    op.create_table(
        "snapshot_template_account_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("token_id", sa.String(length=64), nullable=False),
        sa.Column("account_uuid", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("image_id", sa.BigInteger(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["snapshot_templates.template_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "token_id", name="uq_template_account_state_template_token"),
    )
    op.create_index(
        op.f("ix_snapshot_template_account_states_template_id"),
        "snapshot_template_account_states",
        ["template_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_snapshot_template_account_states_user_id"),
        "snapshot_template_account_states",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_snapshot_template_account_states_token_id"),
        "snapshot_template_account_states",
        ["token_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_snapshot_template_account_states_created_at"),
        "snapshot_template_account_states",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_snapshot_template_account_states_updated_at"),
        "snapshot_template_account_states",
        ["updated_at"],
        unique=False,
    )
