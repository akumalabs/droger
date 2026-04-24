"""add snapshot template account states

Revision ID: 0003_template_account_states
Revises: 0002_snapshot_templates
Create Date: 2026-04-25 00:00:01.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003_template_account_states"
down_revision: Union[str, None] = "0002_snapshot_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("snapshot_templates", "name", new_column_name="label")
    op.alter_column("snapshot_templates", "description", new_column_name="notes")
    op.alter_column("snapshot_templates", "current_token_id", new_column_name="owner_token_id")
    op.alter_column("snapshot_templates", "current_do_uuid", new_column_name="owner_account_uuid")

    op.execute(
        sa.text(
            "UPDATE snapshot_templates "
            "SET status = 'available' "
            "WHERE status = 'ready'"
        )
    )

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

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT template_id, user_id, owner_token_id, owner_account_uuid, current_image_id, status, created_at, updated_at "
            "FROM snapshot_templates"
        )
    ).fetchall()

    for row in rows:
        conn.execute(
            sa.text(
                "INSERT INTO snapshot_template_account_states "
                "(template_id, user_id, token_id, account_uuid, status, image_id, last_error, last_synced_at, created_at, updated_at) "
                "VALUES (:template_id, :user_id, :token_id, :account_uuid, :status, :image_id, NULL, :last_synced_at, :created_at, :updated_at)"
            ),
            {
                "template_id": row.template_id,
                "user_id": row.user_id,
                "token_id": row.owner_token_id,
                "account_uuid": row.owner_account_uuid,
                "status": "available" if row.status in {"available", "ready"} else row.status,
                "image_id": row.current_image_id,
                "last_synced_at": row.updated_at,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            },
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_snapshot_template_account_states_updated_at"), table_name="snapshot_template_account_states")
    op.drop_index(op.f("ix_snapshot_template_account_states_created_at"), table_name="snapshot_template_account_states")
    op.drop_index(op.f("ix_snapshot_template_account_states_token_id"), table_name="snapshot_template_account_states")
    op.drop_index(op.f("ix_snapshot_template_account_states_user_id"), table_name="snapshot_template_account_states")
    op.drop_index(op.f("ix_snapshot_template_account_states_template_id"), table_name="snapshot_template_account_states")
    op.drop_table("snapshot_template_account_states")

    op.alter_column("snapshot_templates", "owner_account_uuid", new_column_name="current_do_uuid")
    op.alter_column("snapshot_templates", "owner_token_id", new_column_name="current_token_id")
    op.alter_column("snapshot_templates", "notes", new_column_name="description")
    op.alter_column("snapshot_templates", "label", new_column_name="name")

    op.execute(
        sa.text(
            "UPDATE snapshot_templates "
            "SET status = 'ready' "
            "WHERE status = 'available'"
        )
    )
