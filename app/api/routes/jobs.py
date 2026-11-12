from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.models import Job
from app.models.enums import JobStatus
from app.schemas.error import ErrorResponse
from app.schemas.job import JobPage, JobRead
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobPage)
def list_jobs(
    db: DbSession,
    status: JobStatus | None = None,
    company_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobPage:
    items, total = JobService(db).list_jobs(
        status=status, company_id=company_id, limit=limit, offset=offset
    )
    return JobPage(
        items=[JobRead.model_validate(job) for job in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{job_id}",
    response_model=JobRead,
    responses={404: {"model": ErrorResponse, "description": "Job not found"}},
)
def get_job(job_id: int, db: DbSession) -> Job:
    return JobService(db).get(job_id)
