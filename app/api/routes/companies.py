from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.models import Company, Job
from app.schemas.company import CompanyCreate, CompanyRead
from app.schemas.job import JobCreate, JobRead
from app.services.company_service import CompanyService
from app.services.job_service import JobService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(data: CompanyCreate, db: DbSession) -> Company:
    return CompanyService(db).create(data)


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(company_id: int, db: DbSession) -> Company:
    return CompanyService(db).get(company_id)


@router.post(
    "/{company_id}/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED
)
def create_job(company_id: int, data: JobCreate, db: DbSession) -> Job:
    return JobService(db).create(company_id, data)
