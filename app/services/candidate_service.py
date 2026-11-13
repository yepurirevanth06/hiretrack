from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import Candidate, Resume
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.resume_repository import ResumeRepository
from app.schemas.candidate import CandidateCreate
from app.schemas.resume import ResumeCreate


class CandidateService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.candidates = CandidateRepository(db)
        self.resumes = ResumeRepository(db)

    def create(self, data: CandidateCreate) -> Candidate:
        email = data.email.lower()
        if self.candidates.get_by_email(email) is not None:
            raise ConflictError("A candidate with this email already exists")

        candidate = Candidate(email=email, full_name=data.full_name, phone=data.phone)
        try:
            self.candidates.add(candidate)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("A candidate with this email already exists") from exc

        self.db.refresh(candidate)
        return candidate

    def get(self, candidate_id: int) -> Candidate:
        candidate = self.candidates.get(candidate_id)
        if candidate is None:
            raise NotFoundError(f"Candidate {candidate_id} not found")
        return candidate

    def add_resume(self, candidate_id: int, data: ResumeCreate) -> Resume:
        self.get(candidate_id)
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
        self.get(candidate_id)
        return self.resumes.list_active(candidate_id)
