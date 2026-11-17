from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.models import AuditEvent


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        actor_user_id: int | None,
        action: str,
        entity_type: str,
        entity_id: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Adds an audit row to the current transaction. It is saved by the
        same commit as the change it describes, or not at all."""
        self.db.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details or {},
            )
        )

    def record_many(self, rows: list[dict[str, Any]]) -> None:
        if rows:
            self.db.execute(insert(AuditEvent), rows)

    def list_for_entity(self, entity_type: str, entity_id: int) -> list[AuditEvent]:
        query = (
            select(AuditEvent)
            .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
            .order_by(AuditEvent.id)
        )
        return list(self.db.scalars(query).all())
