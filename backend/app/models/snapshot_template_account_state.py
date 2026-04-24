from datetime import datetime, timezone
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class SnapshotTemplateAccountState(Base):
    __tablename__ = "snapshot_template_account_states"
    __table_args__ = (
        UniqueConstraint("template_id", "token_id", name="uq_template_account_state_template_token"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[str] = mapped_column(String(64), ForeignKey("snapshot_templates.template_id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    token_id: Mapped[str] = mapped_column(String(64), index=True)
    account_uuid: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    image_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
