from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["health"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/health")
def health(db: DbSession):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
