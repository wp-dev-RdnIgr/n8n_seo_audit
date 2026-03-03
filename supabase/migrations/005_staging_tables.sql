-- ============================================================
-- Migration 005: Create staging tables for shadow sync
-- ============================================================
-- Purpose: Enable "shadow update" pattern where data is synced
-- to staging tables first, then atomically migrated to production.
-- This prevents production DB from being incomplete during sync.
-- ============================================================

-- 1. ws_departments_stg
CREATE TABLE IF NOT EXISTS ws_departments_stg (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

-- 2. ws_users_stg
CREATE TABLE IF NOT EXISTS ws_users_stg (
    id INTEGER PRIMARY KEY,
    name TEXT,
    email TEXT,
    title TEXT,
    role TEXT,
    status TEXT,
    department_id INTEGER REFERENCES ws_departments_stg(id)
);

-- 3. ws_projects_stg
CREATE TABLE IF NOT EXISTS ws_projects_stg (
    id INTEGER PRIMARY KEY,
    name TEXT,
    status TEXT,
    company TEXT,
    page TEXT,
    max_time NUMERIC,
    max_money NUMERIC,
    date_added TIMESTAMPTZ,
    date_start TIMESTAMPTZ,
    date_end TIMESTAMPTZ,
    date_closed TIMESTAMPTZ,
    user_from_id INTEGER REFERENCES ws_users_stg(id),
    user_to_id INTEGER REFERENCES ws_users_stg(id),
    users_raw JSONB,
    last_synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. ws_tasks_stg
CREATE TABLE IF NOT EXISTS ws_tasks_stg (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES ws_projects_stg(id),
    parent_id INTEGER,
    name TEXT,
    text TEXT,
    status TEXT,
    priority INTEGER DEFAULT 0,
    page TEXT,
    date_added TIMESTAMPTZ,
    date_start TIMESTAMPTZ,
    date_end TIMESTAMPTZ,
    date_closed TIMESTAMPTZ,
    user_from_id INTEGER REFERENCES ws_users_stg(id),
    user_to_id INTEGER REFERENCES ws_users_stg(id),
    tags JSONB,
    last_synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. ws_time_logs_stg
CREATE TABLE IF NOT EXISTS ws_time_logs_stg (
    id INTEGER PRIMARY KEY,
    task_id INTEGER REFERENCES ws_tasks_stg(id),
    user_id INTEGER REFERENCES ws_users_stg(id),
    time_str TEXT,
    hours NUMERIC,
    money NUMERIC,
    comment TEXT,
    date_log DATE,
    last_synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. ws_sync_state_stg
CREATE TABLE IF NOT EXISTS ws_sync_state_stg (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize sync state
INSERT INTO ws_sync_state_stg (key, value, updated_at)
VALUES
    ('batch_offset', '0', NOW()),
    ('sync_status', 'idle', NOW())
ON CONFLICT (key) DO NOTHING;

-- ============================================================
-- Migration function: atomic swap staging -> production
-- ============================================================
CREATE OR REPLACE FUNCTION migrate_staging_to_production()
RETURNS TABLE(migrated_departments INT, migrated_users INT, migrated_projects INT, migrated_tasks INT, migrated_time_logs INT) AS $$
DECLARE
    cnt_dept INT;
    cnt_users INT;
    cnt_proj INT;
    cnt_tasks INT;
    cnt_logs INT;
BEGIN
    -- Disable FK checks for the duration
    SET session_replication_role = 'replica';

    -- Clear production tables
    TRUNCATE TABLE ws_time_logs CASCADE;
    TRUNCATE TABLE ws_tasks CASCADE;
    TRUNCATE TABLE ws_projects CASCADE;
    TRUNCATE TABLE ws_users CASCADE;
    TRUNCATE TABLE ws_departments CASCADE;

    -- Copy from staging to production
    INSERT INTO ws_departments (id, name)
    SELECT id, name FROM ws_departments_stg;
    GET DIAGNOSTICS cnt_dept = ROW_COUNT;

    INSERT INTO ws_users (id, name, email, title, role, status, department_id)
    SELECT id, name, email, title, role, status, department_id FROM ws_users_stg;
    GET DIAGNOSTICS cnt_users = ROW_COUNT;

    INSERT INTO ws_projects (id, name, status, company, page, max_time, max_money, date_added, date_start, date_end, date_closed, user_from_id, user_to_id, users_raw, last_synced_at)
    SELECT id, name, status, company, page, max_time, max_money, date_added, date_start, date_end, date_closed, user_from_id, user_to_id, users_raw, last_synced_at FROM ws_projects_stg;
    GET DIAGNOSTICS cnt_proj = ROW_COUNT;

    INSERT INTO ws_tasks (id, project_id, parent_id, name, text, status, priority, page, date_added, date_start, date_end, date_closed, user_from_id, user_to_id, tags, last_synced_at)
    SELECT id, project_id, parent_id, name, text, status, priority, page, date_added, date_start, date_end, date_closed, user_from_id, user_to_id, tags, last_synced_at FROM ws_tasks_stg;
    GET DIAGNOSTICS cnt_tasks = ROW_COUNT;

    INSERT INTO ws_time_logs (id, task_id, user_id, time_str, hours, money, comment, date_log, last_synced_at)
    SELECT id, task_id, user_id, time_str, hours, money, comment, date_log, last_synced_at FROM ws_time_logs_stg;
    GET DIAGNOSTICS cnt_logs = ROW_COUNT;

    -- Re-enable FK checks
    SET session_replication_role = 'origin';

    -- Reset departments sequence
    PERFORM setval('ws_departments_id_seq', COALESCE((SELECT MAX(id) FROM ws_departments), 1));

    -- Update production sync_state
    DELETE FROM ws_sync_state;
    INSERT INTO ws_sync_state (key, value, updated_at)
    VALUES ('batch_offset', '0', NOW());

    RETURN QUERY SELECT cnt_dept, cnt_users, cnt_proj, cnt_tasks, cnt_logs;
END;
$$ LANGUAGE plpgsql;
