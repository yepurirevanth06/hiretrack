"""Row-level security (RLS) context for each database transaction.

Postgres can't see our JWT, so we tell it who is asking. At the start of every
transaction we switch to the restricted `hiretrack_app` role and set two
transaction-local settings that the RLS policies read:

    app.company_id    the recruiter's company (empty for everyone else)
    app.candidate_id  the candidate's profile (empty for everyone else)

`SET LOCAL` lasts only until the transaction ends, so nothing leaks to the next
request that reuses the same pooled connection.
"""

from typing import Any

from sqlalchemy import Connection, event
from sqlalchemy.orm import Session, SessionTransaction

APP_ROLE = "hiretrack_app"
TENANT_KEY = "tenant"
BYPASS_KEY = "rls_bypass"  # tests only: lets test code inspect every row


def set_tenant(db: Session, *, company_id: int | None, candidate_id: int | None) -> None:
    """Remember who the request is for, and apply it to the open transaction."""
    db.info[TENANT_KEY] = {"company_id": company_id, "candidate_id": candidate_id}
    reapply(db)


def reapply(db: Session) -> None:
    if db.in_transaction():
        _apply(db.connection(), db.info)


def _setting(value: int | None) -> str:
    # The values are integer ids from our own database, so int() makes them
    # safe to put in the SQL text (SET doesn't accept bind parameters).
    return "" if value is None else str(int(value))


def _apply(connection: Connection, info: dict[str, Any]) -> None:
    if info.get(BYPASS_KEY):
        connection.exec_driver_sql("SET LOCAL ROLE NONE")
        return
    tenant = info.get(TENANT_KEY) or {}
    connection.exec_driver_sql(
        f"SET LOCAL ROLE {APP_ROLE}; "
        f"SET LOCAL app.company_id = '{_setting(tenant.get('company_id'))}'; "
        f"SET LOCAL app.candidate_id = '{_setting(tenant.get('candidate_id'))}'"
    )


@event.listens_for(Session, "after_begin")
def _on_transaction_begin(
    session: Session, transaction: SessionTransaction, connection: Connection
) -> None:
    _apply(connection, session.info)
