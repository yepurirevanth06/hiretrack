from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.models import Candidate, Resume
from app.schemas.application import ApplicationDetail
from app.schemas.candidate import CandidateCreate, CandidateRead
from app.schemas.error import ErrorResponse
from app.schemas.resume import ResumeCreate, ResumeRead
from app.services.application_service import ApplicationService
from app.services.candidate_service import CandidateService

router = APIRouter(prefix="/candidates", tags=["candidates"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Candidate not found"}}


@router.post(
    "",
    response_model=CandidateRead,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "Email already registered"}},
)
def create_candidate(data: CandidateCreate, db: DbSession) -> Candidate:
    return CandidateService(db).create(data)


@router.get("/{candidate_id}", response_model=CandidateRead, responses=NOT_FOUND)
def get_candidate(candidate_id: int, db: DbSession) -> Candidate:
    return CandidateService(db).get(candidate_id)


@router.post(
    "/{candidate_id}/resumes",
    response_model=ResumeRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        **NOT_FOUND,
        409: {"model": ErrorResponse, "description": "Resume already in library"},
    },
)
def add_resume(candidate_id: int, data: ResumeCreate, db: DbSession) -> Resume:
    return CandidateService(db).add_resume(candidate_id, data)


@router.get("/{candidate_id}/resumes", response_model=list[ResumeRead], responses=NOT_FOUND)
def list_resumes(candidate_id: int, db: DbSession) -> list[Resume]:
    return CandidateService(db).list_resumes(candidate_id)


@router.get(
    "/{candidate_id}/applications",
    response_model=list[ApplicationDetail],
    responses=NOT_FOUND,
)
def list_candidate_applications(candidate_id: int, db: DbSession) -> list[ApplicationDetail]:
    applications = ApplicationService(db).list_for_candidate(candidate_id)
    return [ApplicationDetail.model_validate(app) for app in applications]
