from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    InvalidTransitionError,
    NotFoundError,
)
from app.models import Application, AuditEvent, User
from app.models.enums import ApplicationStatus, JobStatus, UserRole
from app.repositories.application_repository import ApplicationRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.job_repository import JobRepository
from app.repositories.resume_repository import ResumeRepository
from app.services.access import can_view_job, is_company_recruiter
from app.services.application_workflow import can_transition


class ApplicationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.applications = ApplicationRepository(db)
        self.jobs = JobRepository(db)
        self.resumes = ResumeRepository(db)
        self.audit = AuditRepository(db)

    def apply(
        self, job_id: int, candidate_id: int, resume_id: int, *, actor_user_id: int
    ) -> Application:
        job = self.jobs.get(job_id, lock="share")
        if job is None or job.status != JobStatus.OPEN:
            raise NotFoundError(f"Job {job_id} not found")

        resume = self.resumes.get(resume_id)
        if (
            resume is None
            or resume.candidate_id != candidate_id
            or resume.deleted_at is not None
        ):
            raise NotFoundError(f"Resume {resume_id} not found")

        if self.applications.get_by_job_and_candidate(job_id, candidate_id):
            raise ConflictError("You have already applied to this job")

        application = Application(job_id=job_id, candidate_id=candidate_id, resume_id=resume.id)
        try:
            self.applications.add(application)
            self.audit.record(
                actor_user_id=actor_user_id,
                action="application.created",
                entity_type="application",
                entity_id=application.id,
                details={"to": ApplicationStatus.APPLIED.value},
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("You have already applied to this job") from exc

        self.db.refresh(application)
        return application

    def get_for_viewer(self, application_id: int, viewer: User) -> Application:
        application = self.applications.get(application_id)
        if application is None or not self._can_view(application, viewer):
            raise NotFoundError(f"Application {application_id} not found")
        return application

    def _can_view(self, application: Application, viewer: User) -> bool:
        return viewer.candidate_id == application.candidate_id or is_company_recruiter(
            viewer, application.job.company_id
        )

    def change_status(
        self, application_id: int, new_status: ApplicationStatus, user: User
    ) -> Application:
        application = self.applications.get(application_id, for_update=True)
        if application is None or not self._can_view(application, user):
            raise NotFoundError(f"Application {application_id} not found")

        if user.role == UserRole.CANDIDATE and new_status != ApplicationStatus.WITHDRAWN:
            raise ForbiddenError("Candidates can only withdraw their own applications")
        if user.role == UserRole.RECRUITER and new_status == ApplicationStatus.WITHDRAWN:
            raise ForbiddenError("Only the candidate can withdraw an application")

        if application.status == new_status:
            self.db.commit()  # nothing to change; release the row lock
            return application

        if not can_transition(application.status, new_status):
            raise InvalidTransitionError(
                f"Cannot move an application from '{application.status}' to '{new_status}'"
            )

        old_status = application.status
        application.status = new_status
        self.audit.record(
            actor_user_id=user.id,
            action="application.status_changed",
            entity_type="application",
            entity_id=application.id,
            details={"from": old_status.value, "to": new_status.value},
        )
        self.db.commit()  # the status change and its audit row commit together
        self.db.refresh(application)
        return application

    def history(self, application_id: int, viewer: User) -> list[AuditEvent]:
        self.get_for_viewer(application_id, viewer)  # same visibility rules (404)
        return self.audit.list_for_entity("application", application_id)

    def list_for_candidate(self, candidate_id: int) -> list[Application]:
        return self.applications.list_for_candidate(candidate_id)

    def list_for_job(self, job_id: int, user: User) -> list[Application]:
        job = self.jobs.get(job_id)
        if job is None or not can_view_job(user, job):
            raise NotFoundError(f"Job {job_id} not found")
        if not is_company_recruiter(user, job.company_id):
            raise ForbiddenError("Only the job's company can see its applicants")
        return self.applications.list_for_job(job_id)
