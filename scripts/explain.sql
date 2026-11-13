\pset pager off
\timing on

SELECT 'jobs' AS table_name, count(*) FROM jobs
UNION ALL SELECT 'applications', count(*) FROM applications;

\echo '=== 1. All jobs, newest first ==='
EXPLAIN ANALYZE SELECT * FROM jobs ORDER BY created_at DESC, id DESC LIMIT 20;

\echo '=== 2. Open jobs, newest first ==='
EXPLAIN ANALYZE SELECT * FROM jobs WHERE status = 'open' ORDER BY created_at DESC, id DESC LIMIT 20;

\echo '=== 3. Deep page of open jobs ==='
EXPLAIN ANALYZE SELECT * FROM jobs WHERE status = 'open' ORDER BY created_at DESC, id DESC LIMIT 20 OFFSET 90000;

\echo '=== 4. Count all jobs ==='
EXPLAIN ANALYZE SELECT count(*) FROM jobs;

\echo '=== 5. Applications by status (no index starts with status) ==='
EXPLAIN ANALYZE SELECT * FROM applications WHERE status = 'applied' LIMIT 20;

\echo '=== 6. Applications by job_id (index starts with job_id) ==='
EXPLAIN ANALYZE SELECT * FROM applications WHERE job_id = 500;
