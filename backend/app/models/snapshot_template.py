from datetime import datetime, timezone
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class SnapshotTemplate(Base):
    __tablename__ = "snapshot_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_id: Mapped[int] = mapped_column(BigInteger)
    current_image_id: Mapped[int] = mapped_column(BigInteger)
    source_droplet_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    snapshot_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_token_id: Mapped[str] = mapped_column(String(64), index=True)
    owner_account_uuid: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="available")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
