from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.models import Application
from app.schemas.application import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationStatusUpdate,
)
from app.schemas.error import ErrorResponse
from app.services.application_service import ApplicationService

router = APIRouter(tags=["applications"])

APPLICATION_NOT_FOUND = {404: {"model": ErrorResponse, "description": "Application not found"}}


@router.post(
    "/jobs/{job_id}/applications",
    response_model=ApplicationRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse, "description": "Job, candidate or resume not found"},
        409: {"model": ErrorResponse, "description": "Job not open, or already applied"},
    },
)
def apply_to_job(job_id: int, data: ApplicationCreate, db: DbSession) -> Application:
    return ApplicationService(db).apply(job_id, data)


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationRead,
    responses=APPLICATION_NOT_FOUND,
)
def get_application(application_id: int, db: DbSession) -> Application:
    return ApplicationService(db).get(application_id)


@router.patch(
    "/applications/{application_id}/status",
    response_model=ApplicationRead,
    responses={
        **APPLICATION_NOT_FOUND,
        409: {"model": ErrorResponse, "description": "Status change not allowed"},
    },
)
def change_application_status(
    application_id: int, data: ApplicationStatusUpdate, db: DbSession
) -> Application:
    return ApplicationService(db).change_status(application_id, data.status)
