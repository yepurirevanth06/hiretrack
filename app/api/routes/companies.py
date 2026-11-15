from fastapi import APIRouter, status

from app.api.deps import CurrentRecruiter, DbSession
from app.api.responses import AUTH_ERRORS, error
from app.models import Company, Job
from app.schemas.company import CompanyRead
from app.schemas.job import JobCreate, JobRead
from app.services.company_service import CompanyService
from app.services.job_service import JobService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/{company_id}", response_model=CompanyRead, responses=error(404, "Company not found"))
def get_company(company_id: int, db: DbSession) -> Company:
    return CompanyService(db).get(company_id)


@router.post(
    "/{company_id}/jobs",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
    responses={**AUTH_ERRORS, **error(404, "Company not found")},
)
def create_job(
    company_id: int, data: JobCreate, db: DbSession, user: CurrentRecruiter
) -> Job:
    return JobService(db).create(company_id, data, user)
