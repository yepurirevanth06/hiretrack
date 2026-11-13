from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.models import Job
from app.models.enums import JobStatus
from app.schemas.error import ErrorResponse
from app.schemas.job import JobCloseResult, JobPage, JobRead
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])

JOB_NOT_FOUND = {404: {"model": ErrorResponse, "description": "Job not found"}}


@router.get(
    "",
    response_model=JobPage,
    responses={400: {"model": ErrorResponse, "description": "Invalid cursor"}},
)
def list_jobs(
    db: DbSession,
    status: JobStatus | None = None,
    company_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
    include_total: bool = False,
) -> JobPage:
    items, next_cursor, total = JobService(db).list_jobs(
        status=status,
        company_id=company_id,
        limit=limit,
        cursor=cursor,
        include_total=include_total,
    )
    return JobPage(
        items=[JobRead.model_validate(job) for job in items],
        next_cursor=next_cursor,
        total=total,
    )


@router.get("/{job_id}", response_model=JobRead, responses=JOB_NOT_FOUND)
def get_job(job_id: int, db: DbSession) -> Job:
    return JobService(db).get(job_id)


@router.post("/{job_id}/close", response_model=JobCloseResult, responses=JOB_NOT_FOUND)
def close_job(job_id: int, db: DbSession) -> JobCloseResult:
    job, rejected = JobService(db).close(job_id)
    return JobCloseResult(job=JobRead.model_validate(job), rejected_applications=rejected)
