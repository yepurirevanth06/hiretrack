from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.pagination import decode_cursor, encode_cursor
from app.models import Job
from app.models.enums import JobStatus
from app.repositories.application_repository import ApplicationRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobCreate


class JobService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.jobs = JobRepository(db)
        self.companies = CompanyRepository(db)

    def create(self, company_id: int, data: JobCreate) -> Job:
        if self.companies.get(company_id) is None:
            raise NotFoundError(f"Company {company_id} not found")

        job = Job(company_id=company_id, **data.model_dump())
        self.jobs.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, job_id: int) -> Job:
        job = self.jobs.get(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found")
        return job

    def list_jobs(
        self,
        *,
        status: JobStatus | None,
        company_id: int | None,
        limit: int,
        cursor: str | None,
        include_total: bool,
    ) -> tuple[list[Job], str | None, int | None]:
        after = decode_cursor(cursor) if cursor else None

        rows = self.jobs.find_page(
            status=status, company_id=company_id, limit=limit + 1, after=after
        )
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more else None

        total = (
            self.jobs.count(status=status, company_id=company_id) if include_total else None
        )
        return items, next_cursor, total

    def close(self, job_id: int) -> tuple[Job, int]:
        job = self.jobs.get(job_id, lock="update")
        if job is None:
            raise NotFoundError(f"Job {job_id} not found")

        if job.status == JobStatus.CLOSED:
            self.db.commit()  # already closed; release the lock
            return job, 0

        job.status = JobStatus.CLOSED
        rejected = ApplicationRepository(self.db).reject_active_for_job(job_id)
        self.db.commit()
        self.db.refresh(job)
        return job, rejected
