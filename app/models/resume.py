from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.candidate import Candidate


class Resume(TimestampMixin, Base):
    __tablename__ = "resumes"
    __table_args__ = (UniqueConstraint("candidate_id", "file_hash"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(200))
    file_key: Mapped[str] = mapped_column(String(500))
    file_hash: Mapped[str] = mapped_column(String(64))
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True))

    candidate: Mapped["Candidate"] = relationship(back_populates="resumes")
