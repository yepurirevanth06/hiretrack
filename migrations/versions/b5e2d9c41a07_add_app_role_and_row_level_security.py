"""add app role and row level security

Revision ID: b5e2d9c41a07
Revises: af48f4a36e74
Create Date: 2026-11-17 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b5e2d9c41a07'
down_revision: Union[str, Sequence[str], None] = 'af48f4a36e74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Written by hand: autogenerate doesn't know about roles, grants or policies.
# Kept as a frozen copy (not imported from app/db/rls.py) so this migration
# always does the same thing, even if the app code changes later.


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'hiretrack_app') THEN
                CREATE ROLE hiretrack_app NOLOGIN;
            END IF;
        END
        $$
    """)
    op.execute("GRANT USAGE ON SCHEMA public TO hiretrack_app")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO hiretrack_app"
    )
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO hiretrack_app")
    op.execute("REVOKE UPDATE, DELETE ON audit_events FROM hiretrack_app")
    # Tables created by later migrations get the same privileges automatically.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hiretrack_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO hiretrack_app"
    )

    op.execute("ALTER TABLE applications ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY applications_tenant_isolation ON applications
        USING (
            candidate_id = NULLIF(current_setting('app.candidate_id', true), '')::bigint
            OR job_id IN (
                SELECT id FROM jobs
                WHERE company_id = NULLIF(current_setting('app.company_id', true), '')::bigint
            )
        )
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP POLICY IF EXISTS applications_tenant_isolation ON applications")
    op.execute("ALTER TABLE applications DISABLE ROW LEVEL SECURITY")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM hiretrack_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM hiretrack_app"
    )
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM hiretrack_app")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM hiretrack_app")
    op.execute("REVOKE USAGE ON SCHEMA public FROM hiretrack_app")
    # The role itself is left in place: roles belong to the whole Postgres
    # server, and another database (like hiretrack_test) may still use it.
