from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import EmploymentType, JobStatus, enum_column

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.company import Company


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_company_id_status", "company_id", "status"),
        Index("ix_jobs_status_created_at", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(200))
    employment_type: Mapped[EmploymentType] = mapped_column(
        enum_column(EmploymentType, "employment_type")
    )
    status: Mapped[JobStatus] = mapped_column(
        enum_column(JobStatus, "job_status"),
        default=JobStatus.DRAFT,
        server_default=JobStatus.DRAFT.value,
    )

    company: Mapped["Company"] = relationship(back_populates="jobs")
    applications: Mapped[list["Application"]
                         ] = relationship(back_populates="job")
