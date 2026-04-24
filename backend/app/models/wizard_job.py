from datetime import datetime, timezone
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class WizardJob(Base):
    __tablename__ = "wizard_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    token_id: Mapped[str] = mapped_column(String(64), index=True)
    droplet_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    windows_version: Mapped[str] = mapped_column(String(64))
    rdp_port: Mapped[int] = mapped_column(Integer)
    command: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
