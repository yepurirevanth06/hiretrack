from fastapi import APIRouter, status

from app.api.deps import CurrentCandidate, DbSession
from app.api.responses import AUTH_ERRORS, error
from app.models import Resume
from app.schemas.application import ApplicationDetail
from app.schemas.resume import ResumeCreate, ResumeRead
from app.services.application_service import ApplicationService
from app.services.candidate_service import CandidateService

router = APIRouter(prefix="/me", tags=["me"])


@router.post(
    "/resumes",
    response_model=ResumeRead,
    status_code=status.HTTP_201_CREATED,
    responses={**AUTH_ERRORS, **error(409, "Resume already in library")},
)
def add_my_resume(data: ResumeCreate, db: DbSession, user: CurrentCandidate) -> Resume:
    return CandidateService(db).add_resume(user.candidate_id, data)


@router.get("/resumes", response_model=list[ResumeRead], responses=AUTH_ERRORS)
def list_my_resumes(db: DbSession, user: CurrentCandidate) -> list[Resume]:
    return CandidateService(db).list_resumes(user.candidate_id)


@router.get("/applications", response_model=list[ApplicationDetail], responses=AUTH_ERRORS)
def list_my_applications(db: DbSession, user: CurrentCandidate) -> list[ApplicationDetail]:
    applications = ApplicationService(db).list_for_candidate(user.candidate_id)
    return [ApplicationDetail.model_validate(app) for app in applications]
