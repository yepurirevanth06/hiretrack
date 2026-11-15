from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.api.responses import AUTH_ERRORS, error
from app.models import Candidate
from app.schemas.candidate import CandidateRead
from app.services.candidate_service import CandidateService

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get(
    "/{candidate_id}",
    response_model=CandidateRead,
    responses={**AUTH_ERRORS, **error(404, "Candidate not found")},
)
def get_candidate(candidate_id: int, db: DbSession, user: CurrentUser) -> Candidate:
    return CandidateService(db).get_for_viewer(candidate_id, user)
