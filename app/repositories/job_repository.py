from datetime import datetime
from typing import Literal

from sqlalchemy import Select, func, select, tuple_
from sqlalchemy.orm import Session

from app.models import Job
from app.models.enums import JobStatus


class JobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, job_id: int, *, lock: Literal["update", "share"] | None = None) -> Job | None:
        if lock is None:
            return self.db.get(Job, job_id)
        query = (
            select(Job)
            .where(Job.id == job_id)
            .with_for_update(read=(lock == "share"))
            .execution_options(populate_existing=True)
        )
        return self.db.scalar(query)

    def add(self, job: Job) -> Job:
        self.db.add(job)
        self.db.flush()
        return job

    def _filtered(self, status: JobStatus | None, company_id: int | None) -> Select:
        query = select(Job)
        if status is not None:
            query = query.where(Job.status == status)
        if company_id is not None:
            query = query.where(Job.company_id == company_id)
        return query

    def find_page(
        self,
        *,
        status: JobStatus | None,
        company_id: int | None,
        limit: int,
        after: tuple[datetime, int] | None,
    ) -> list[Job]:
        query = self._filtered(status, company_id)
        if after is not None:
            query = query.where(tuple_(Job.created_at, Job.id) < tuple_(*after))
        query = query.order_by(Job.created_at.desc(), Job.id.desc()).limit(limit)
        return list(self.db.scalars(query).all())

    def count(self, *, status: JobStatus | None, company_id: int | None) -> int:
        query = self._filtered(status, company_id)
        return self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
