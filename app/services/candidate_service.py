from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import Candidate, Resume, User
from app.models.enums import UserRole
from app.repositories.application_repository import ApplicationRepository
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.resume_repository import ResumeRepository
from app.schemas.resume import ResumeCreate


class CandidateService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.candidates = CandidateRepository(db)
        self.resumes = ResumeRepository(db)
        self.applications = ApplicationRepository(db)

    def get_for_viewer(self, candidate_id: int, viewer: User) -> Candidate:
        candidate = self.candidates.get(candidate_id)
        if candidate is None or not self._can_view(candidate_id, viewer):
            raise NotFoundError(f"Candidate {candidate_id} not found")
        return candidate

    def _can_view(self, candidate_id: int, viewer: User) -> bool:
        if viewer.candidate_id == candidate_id:
            return True
        return (
            viewer.role == UserRole.RECRUITER
            and viewer.company_id is not None
            and self.applications.candidate_applied_to_company(candidate_id, viewer.company_id)
        )

    def add_resume(self, candidate_id: int, data: ResumeCreate) -> Resume:
        if self.resumes.get_by_hash(candidate_id, data.file_hash) is not None:
            raise ConflictError("This resume file is already in your library")

        resume = Resume(candidate_id=candidate_id, **data.model_dump())
        try:
            self.resumes.add(resume)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("This resume file is already in your library") from exc

        self.db.refresh(resume)
        return resume

    def list_resumes(self, candidate_id: int) -> list[Resume]:
        return self.resumes.list_active(candidate_id)
