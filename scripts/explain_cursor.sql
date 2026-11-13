\pset pager off

\echo '=== OFFSET: open jobs at position 90,000 ==='
EXPLAIN ANALYZE SELECT * FROM jobs WHERE status = 'open'
ORDER BY created_at DESC, id DESC LIMIT 20 OFFSET 90000;

SELECT created_at AS c, id AS i FROM jobs WHERE status = 'open'
ORDER BY created_at DESC, id DESC OFFSET 89999 LIMIT 1 \gset

\echo '=== CURSOR: the same page, starting after the last job seen ==='
EXPLAIN ANALYZE SELECT * FROM jobs WHERE status = 'open'
AND (created_at, id) < (:'c', :i)
ORDER BY created_at DESC, id DESC LIMIT 20;
