from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api.deps import DbSession
from app.core.exceptions import ServiceUnavailableError
from app.schemas.error import ErrorResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    responses={503: {"model": ErrorResponse, "description": "Database unavailable"}},
)
def health(db: DbSession):
    try:
        db.execute(text("SELECT 1"))
    except OperationalError as exc:
        raise ServiceUnavailableError("Database is unavailable") from exc
    return {"status": "ok", "database": "ok"}
