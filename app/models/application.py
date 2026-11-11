from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import ApplicationStatus, enum_column

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.job import Job
    from app.models.resume import Resume


class Application(TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id"),
        Index("ix_applications_candidate_id", "candidate_id"),
        Index("ix_applications_job_id_status", "job_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="RESTRICT"))
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="RESTRICT")
    )
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="RESTRICT")
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        enum_column(ApplicationStatus, "application_status"),
        default=ApplicationStatus.APPLIED,
        server_default=ApplicationStatus.APPLIED.value,
    )

    job: Mapped["Job"] = relationship(back_populates="applications")
    candidate: Mapped["Candidate"] = relationship(
        back_populates="applications")
    resume: Mapped["Resume"] = relationship()
