from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentRecruiter, DbSession, OptionalUser
from app.api.responses import AUTH_ERRORS, error
from app.models import Job
from app.models.enums import JobStatus
from app.schemas.job import JobCloseResult, JobPage, JobRead
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "",
    response_model=JobPage,
    responses={**error(400, "Invalid cursor"), **error(401, "Invalid token")},
)
def list_jobs(
    db: DbSession,
    viewer: OptionalUser,
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
        viewer=viewer,
    )
    return JobPage(
        items=[JobRead.model_validate(job) for job in items],
        next_cursor=next_cursor,
        total=total,
    )


@router.get("/{job_id}", response_model=JobRead, responses=error(404, "Job not found"))
def get_job(job_id: int, db: DbSession, viewer: OptionalUser) -> Job:
    return JobService(db).get(job_id, viewer)


@router.post(
    "/{job_id}/close",
    response_model=JobCloseResult,
    responses={**AUTH_ERRORS, **error(404, "Job not found")},
)
def close_job(job_id: int, db: DbSession, user: CurrentRecruiter) -> JobCloseResult:
    job, rejected = JobService(db).close(job_id, user)
    return JobCloseResult(job=JobRead.model_validate(job), rejected_applications=rejected)
