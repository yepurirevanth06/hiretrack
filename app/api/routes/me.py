from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status

from app.ai.llm import LLMClient, get_llm
from app.api.deps import CurrentCandidate, DbSession
from app.api.responses import AUTH_ERRORS, error
from app.core.exceptions import PayloadTooLargeError
from app.models import Resume
from app.schemas.application import ApplicationDetail
from app.schemas.resume import ResumeCreate, ResumeRead
from app.schemas.resume_profile import ResumeProfileRead
from app.services.application_service import ApplicationService
from app.services.candidate_service import CandidateService
from app.services.resume_ai_service import ResumeAIService

MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB is plenty for a text resume
LLM = Annotated[LLMClient, Depends(get_llm)]

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


@router.post(
    "/resumes/{resume_id}/parse",
    response_model=ResumeProfileRead,
    responses={
        **AUTH_ERRORS,
        **error(404, "Resume not found"),
        **error(413, "File too large"),
        **error(422, "Unreadable file"),
        **error(502, "AI returned an unusable answer"),
        **error(503, "AI service unavailable"),
    },
)
def parse_my_resume(
    resume_id: int, file: UploadFile, db: DbSession, user: CurrentCandidate, llm: LLM
) -> ResumeProfileRead:
    """Upload the resume file (PDF or text). An LLM extracts skills, experience and
    education into structured data."""
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise PayloadTooLargeError("Resume files can be at most 2 MB")
    profile, cached = ResumeAIService(db, llm).parse(
        resume_id, user, content, file.content_type
    )
    return ResumeProfileRead.model_validate(profile).model_copy(update={"cached": cached})


@router.get(
    "/resumes/{resume_id}/profile",
    response_model=ResumeProfileRead,
    responses={**AUTH_ERRORS, **error(404, "Resume not found or not parsed yet")},
)
def get_my_resume_profile(
    resume_id: int, db: DbSession, user: CurrentCandidate
) -> ResumeProfileRead:
    profile = ResumeAIService(db).get_profile(resume_id, user)
    return ResumeProfileRead.model_validate(profile)
