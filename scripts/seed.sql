\timing on
BEGIN;

TRUNCATE applications, resumes, candidates, jobs, companies RESTART IDENTITY;

INSERT INTO companies (name, slug)
SELECT 'Company ' || i, 'company-' || i
FROM generate_series(1, 1000) AS i;

INSERT INTO jobs (company_id, title, description, location, employment_type, status, created_at, updated_at)
SELECT
    (i % 1000) + 1,
    (ARRAY['Backend Engineer', 'Data Engineer', 'Frontend Developer', 'DevOps Engineer', 'ML Engineer'])[(i % 5) + 1] || ' #' || i,
    'Seeded job description ' || i,
    (ARRAY['Remote', 'Fairfax, VA', 'New York, NY', 'Austin, TX', 'Seattle, WA'])[((i / 5) % 5) + 1],
    (ARRAY['full_time', 'part_time', 'contract', 'internship'])[(i % 4) + 1],
    CASE WHEN i % 10 = 0 THEN 'open' WHEN i % 10 = 1 THEN 'draft' ELSE 'closed' END,
    ts,
    ts
FROM (
    SELECT i, now() - random() * interval '730 days' AS ts
    FROM generate_series(1, 1000000) AS i
) AS s;

INSERT INTO candidates (email, full_name)
SELECT 'candidate' || i || '@example.com', 'Candidate ' || i
FROM generate_series(1, 100000) AS i;

INSERT INTO resumes (candidate_id, name, file_key, file_hash)
SELECT id, 'Resume', 'resumes/' || id || '/v1.pdf', md5(id::text) || md5((id * 2)::text)
FROM candidates;

INSERT INTO applications (job_id, candidate_id, resume_id)
SELECT ((c.id * 7 + k * 100003) % 1000000) + 1, c.id, r.id
FROM candidates AS c
JOIN resumes AS r ON r.candidate_id = c.id
CROSS JOIN generate_series(0, 2) AS k;

INSERT INTO applications (job_id, candidate_id, resume_id)
SELECT 900000 + k, 1, 1
FROM generate_series(1, 50) AS k
ON CONFLICT DO NOTHING;

COMMIT;

ANALYZE;

SELECT 'jobs' AS table_name, count(*) FROM jobs
UNION ALL SELECT 'candidates', count(*) FROM candidates
UNION ALL SELECT 'applications', count(*) FROM applications;
