from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Job
from app.models.enums import JobStatus


class JobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, job_id: int) -> Job | None:
        return self.db.get(Job, job_id)

    def add(self, job: Job) -> Job:
        self.db.add(job)
        self.db.flush()
        return job

    def find_page(
        self,
        *,
        status: JobStatus | None,
        company_id: int | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Job], int]:
        query = select(Job)
        if status is not None:
            query = query.where(Job.status == status)
        if company_id is not None:
            query = query.where(Job.company_id == company_id)

        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = self.db.scalars(
            query.order_by(Job.created_at.desc(), Job.id.desc()).limit(limit).offset(offset)
        ).all()
        return list(items), total
