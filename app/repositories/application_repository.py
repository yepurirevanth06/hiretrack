from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.models import Application
from app.models.enums import ApplicationStatus
from app.services.application_workflow import ACTIVE_STATUSES


class ApplicationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, application_id: int, *, for_update: bool = False) -> Application | None:
        query = select(Application).where(Application.id == application_id)
        if for_update:
            query = query.with_for_update().execution_options(populate_existing=True)
        return self.db.scalar(query)

    def get_by_job_and_candidate(self, job_id: int, candidate_id: int) -> Application | None:
        return self.db.scalar(
            select(Application).where(
                Application.job_id == job_id, Application.candidate_id == candidate_id
            )
        )

    def list_for_candidate(self, candidate_id: int) -> list[Application]:
        query = (
            select(Application)
            .options(joinedload(Application.job), joinedload(Application.resume))
            .where(Application.candidate_id == candidate_id)
            .order_by(Application.created_at.desc(), Application.id.desc())
        )
        return list(self.db.scalars(query).all())

    def add(self, application: Application) -> Application:
        self.db.add(application)
        self.db.flush()
        return application

    def reject_active_for_job(self, job_id: int) -> int:
        result = self.db.execute(
            update(Application)
            .where(
                Application.job_id == job_id,
                Application.status.in_(ACTIVE_STATUSES),
            )
            .values(status=ApplicationStatus.REJECTED, updated_at=func.now())
        )
        return result.rowcount
