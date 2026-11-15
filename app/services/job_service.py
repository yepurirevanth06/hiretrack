from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.pagination import decode_cursor, encode_cursor
from app.models import Job, User
from app.models.enums import JobStatus
from app.repositories.application_repository import ApplicationRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobCreate
from app.services.access import can_view_job, is_company_recruiter


class JobService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.jobs = JobRepository(db)
        self.companies = CompanyRepository(db)

    def create(self, company_id: int, data: JobCreate, user: User) -> Job:
        if self.companies.get(company_id) is None:
            raise NotFoundError(f"Company {company_id} not found")
        if not is_company_recruiter(user, company_id):
            raise ForbiddenError("You can only post jobs for your own company")

        job = Job(company_id=company_id, **data.model_dump())
        self.jobs.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, job_id: int, viewer: User | None) -> Job:
        job = self.jobs.get(job_id)
        if job is None or not can_view_job(viewer, job):
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
        viewer: User | None,
    ) -> tuple[list[Job], str | None, int | None]:
        after = decode_cursor(cursor) if cursor else None

        sees_all_statuses = company_id is not None and is_company_recruiter(viewer, company_id)
        if not sees_all_statuses:
            if status not in (None, JobStatus.OPEN):
                return [], None, (0 if include_total else None)
            status = JobStatus.OPEN

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

    def close(self, job_id: int, user: User) -> tuple[Job, int]:
        job = self.jobs.get(job_id, lock="update")
        if job is None or not can_view_job(user, job):
            raise NotFoundError(f"Job {job_id} not found")
        if not is_company_recruiter(user, job.company_id):
            raise ForbiddenError("You can only close your own company's jobs")

        if job.status == JobStatus.CLOSED:
            self.db.commit()  # already closed; release the lock
            return job, 0

        job.status = JobStatus.CLOSED
        rejected = ApplicationRepository(self.db).reject_active_for_job(job_id)
        self.db.commit()
        self.db.refresh(job)
        return job, rejected
