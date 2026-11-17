"""Database-level access rules: the restricted app role, its privileges, and
the row-level security policy on applications.

The migration runs the same statements on real databases. These hooks run them
after create_all(), which is how the test database is built.
"""

from sqlalchemy import DDL, event

from app.db.base import Base

STATEMENTS = [
    # A role the API switches into. It can't log in, isn't a superuser and
    # doesn't own the tables, so RLS policies apply to it.
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'hiretrack_app') THEN
            CREATE ROLE hiretrack_app NOLOGIN;
        END IF;
    END
    $$
    """,
    "GRANT USAGE ON SCHEMA public TO hiretrack_app",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO hiretrack_app",
    "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO hiretrack_app",
    # Least privilege: the app may add audit rows and read them, nothing else.
    "REVOKE UPDATE, DELETE ON audit_events FROM hiretrack_app",
    "ALTER TABLE applications ENABLE ROW LEVEL SECURITY",
    # A row is visible (and writable) only to the candidate who owns it or to
    # the recruiters of the company that owns the job. With no context set,
    # both settings are empty and no rows match.
    """
    CREATE POLICY applications_tenant_isolation ON applications
    USING (
        candidate_id = NULLIF(current_setting('app.candidate_id', true), '')::bigint
        OR job_id IN (
            SELECT id FROM jobs
            WHERE company_id = NULLIF(current_setting('app.company_id', true), '')::bigint
        )
    )
    """,
]

for statement in STATEMENTS:
    event.listen(Base.metadata, "after_create", DDL(statement))
