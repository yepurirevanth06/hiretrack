import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_hash(self, token_hash: str, *, for_update: bool = False) -> RefreshToken | None:
        query = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        if for_update:
            query = query.with_for_update().execution_options(populate_existing=True)
        return self.db.scalar(query)

    def add(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        self.db.flush()
        return token

    def revoke_family(self, family_id: uuid.UUID) -> int:
        result = self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=func.now(), updated_at=func.now())
        )
        return result.rowcount

    def revoke_all_for_user(self, user_id: int) -> int:
        result = self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=func.now(), updated_at=func.now())
        )
        return result.rowcount
