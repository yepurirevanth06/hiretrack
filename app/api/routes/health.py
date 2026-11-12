from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.deps import DbSession
from app.core.exceptions import ServiceUnavailableError

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DbSession):
    try:
        db.execute(text("SELECT 1"))
    except OperationalError as exc:
        raise ServiceUnavailableError("Database is unavailable") from exc
    return {"status": "ok", "database": "ok"}
