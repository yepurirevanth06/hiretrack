from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, InvalidTransitionError, NotFoundError
from app.models import Application
from app.models.enums import ApplicationStatus, JobStatus
from app.repositories.application_repository import ApplicationRepository
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.job_repository import JobRepository
from app.repositories.resume_repository import ResumeRepository
from app.schemas.application import ApplicationCreate
from app.services.application_workflow import can_transition


class ApplicationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.applications = ApplicationRepository(db)
        self.jobs = JobRepository(db)
        self.candidates = CandidateRepository(db)
        self.resumes = ResumeRepository(db)

    def apply(self, job_id: int, data: ApplicationCreate) -> Application:
        job = self.jobs.get(job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found")
        if job.status != JobStatus.OPEN:
            raise ConflictError("This job is not accepting applications")

        if self.candidates.get(data.candidate_id) is None:
            raise NotFoundError(f"Candidate {data.candidate_id} not found")

        resume = self.resumes.get(data.resume_id)
        if (
            resume is None
            or resume.candidate_id != data.candidate_id
            or resume.deleted_at is not None
        ):
            raise NotFoundError(f"Resume {data.resume_id} not found")

        if self.applications.get_by_job_and_candidate(job_id, data.candidate_id):
            raise ConflictError("You have already applied to this job")

        application = Application(
            job_id=job_id, candidate_id=data.candidate_id, resume_id=resume.id
        )
        try:
            self.applications.add(application)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("You have already applied to this job") from exc

        self.db.refresh(application)
        return application

    def get(self, application_id: int) -> Application:
        application = self.applications.get(application_id)
        if application is None:
            raise NotFoundError(f"Application {application_id} not found")
        return application

    def change_status(
        self, application_id: int, new_status: ApplicationStatus
    ) -> Application:
        application = self.applications.get(application_id, for_update=True)
        if application is None:
            raise NotFoundError(f"Application {application_id} not found")

        if application.status == new_status:
            self.db.commit()  # nothing to change; release the row lock
            return application

        if not can_transition(application.status, new_status):
            raise InvalidTransitionError(
                f"Cannot move an application from '{application.status}' to '{new_status}'"
            )

        application.status = new_status
        self.db.commit()
        self.db.refresh(application)
        return application

    def list_for_candidate(self, candidate_id: int) -> list[Application]:
        if self.candidates.get(candidate_id) is None:
            raise NotFoundError(f"Candidate {candidate_id} not found")
        return self.applications.list_for_candidate(candidate_id)
