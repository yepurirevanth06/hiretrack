from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
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
        offset: int,
    ) -> tuple[list[Job], int]:
        return self.jobs.find_page(
            status=status, company_id=company_id, limit=limit, offset=offset
        )

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
