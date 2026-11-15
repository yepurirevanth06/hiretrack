from app.models import Job, User
from app.models.enums import JobStatus, UserRole


def is_company_recruiter(user: User | None, company_id: int) -> bool:
    return (
        user is not None
        and user.role == UserRole.RECRUITER
        and user.company_id == company_id
    )


def can_view_job(user: User | None, job: Job) -> bool:
    return job.status == JobStatus.OPEN or is_company_recruiter(user, job.company_id)
