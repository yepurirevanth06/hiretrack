from fastapi import APIRouter, status

from app.api.deps import CurrentCandidate, CurrentRecruiter, CurrentUser, DbSession
from app.api.responses import AUTH_ERRORS, error
from app.models import Application
from app.schemas.application import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationStatusUpdate,
)
from app.services.application_service import ApplicationService

router = APIRouter(tags=["applications"])


@router.post(
    "/jobs/{job_id}/applications",
    response_model=ApplicationRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        **AUTH_ERRORS,
        **error(404, "Job or resume not found"),
        **error(409, "Already applied"),
    },
)
def apply_to_job(
    job_id: int, data: ApplicationCreate, db: DbSession, user: CurrentCandidate
) -> Application:
    return ApplicationService(db).apply(job_id, user.candidate_id, data.resume_id)


@router.get(
    "/jobs/{job_id}/applications",
    response_model=list[ApplicationRead],
    responses={**AUTH_ERRORS, **error(404, "Job not found")},
)
def list_job_applications(
    job_id: int, db: DbSession, user: CurrentRecruiter
) -> list[Application]:
    return ApplicationService(db).list_for_job(job_id, user)


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationRead,
    responses={**AUTH_ERRORS, **error(404, "Application not found")},
)
def get_application(application_id: int, db: DbSession, user: CurrentUser) -> Application:
    return ApplicationService(db).get_for_viewer(application_id, user)


@router.patch(
    "/applications/{application_id}/status",
    response_model=ApplicationRead,
    responses={
        **AUTH_ERRORS,
        **error(404, "Application not found"),
        **error(409, "Status change not allowed"),
    },
)
def change_application_status(
    application_id: int, data: ApplicationStatusUpdate, db: DbSession, user: CurrentUser
) -> Application:
    return ApplicationService(db).change_status(application_id, data.status, user)
