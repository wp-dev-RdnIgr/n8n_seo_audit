-- =============================================
-- 002: Error retry system
-- Adds resolved/unresolved tracking to error_logs
-- and a function for detecting stale tasks
-- =============================================

-- 1. Add resolved status columns to error_logs
ALTER TABLE error_logs
  ADD COLUMN IF NOT EXISTS resolved BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS queue_id TEXT,
  ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;

-- 2. Index for fast lookup of unresolved errors
CREATE INDEX IF NOT EXISTS idx_error_logs_resolved ON error_logs(resolved);
CREATE INDEX IF NOT EXISTS idx_error_logs_queue_id ON error_logs(queue_id);

-- 3. Function: find stale tasks (stuck in processing > N minutes)
CREATE OR REPLACE FUNCTION find_stale_tasks(stale_minutes INTEGER DEFAULT 10)
RETURNS SETOF task_queue
LANGUAGE sql
STABLE
AS $$
  SELECT *
  FROM task_queue
  WHERE status = 'processing'
    AND updated_at < now() - (stale_minutes || ' minutes')::INTERVAL;
$$;

-- 4. Function: detect stale tasks, log errors, and reset to pending
CREATE OR REPLACE FUNCTION handle_stale_tasks(stale_minutes INTEGER DEFAULT 10)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
  stale RECORD;
  cnt INTEGER := 0;
BEGIN
  FOR stale IN
    SELECT *
    FROM task_queue
    WHERE status = 'processing'
      AND updated_at < now() - (stale_minutes || ' minutes')::INTERVAL
  LOOP
    -- Log the error
    INSERT INTO error_logs (task_id, robot_type, period, sites, status, error_message, queue_id, resolved)
    VALUES (
      stale.task_id,
      'stale_task',
      stale.period,
      stale.sites_list,
      'timeout',
      'Task stuck in processing for >' || stale_minutes || ' min. Auto-reset to pending.',
      stale.queue_id,
      FALSE
    );

    -- Reset the task to pending
    UPDATE task_queue
    SET status = 'pending',
        task_id = NULL,
        error_message = 'Auto-retried: was stuck in processing'
    WHERE id = stale.id;

    cnt := cnt + 1;
  END LOOP;

  RETURN cnt;
END;
$$;

-- 5. Function: mark error as resolved when matching data arrives
CREATE OR REPLACE FUNCTION auto_resolve_errors()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  -- When a task completes (status → 'done'), resolve matching unresolved errors
  IF NEW.status = 'done' AND OLD.status != 'done' THEN
    UPDATE error_logs
    SET resolved = TRUE,
        resolved_at = now()
    WHERE queue_id = NEW.queue_id
      AND resolved = FALSE;
  END IF;
  RETURN NEW;
END;
$$;

-- 6. Trigger: auto-resolve errors when task completes
DROP TRIGGER IF EXISTS trg_auto_resolve_errors ON task_queue;
CREATE TRIGGER trg_auto_resolve_errors
  AFTER UPDATE ON task_queue
  FOR EACH ROW
  EXECUTE FUNCTION auto_resolve_errors();

COMMENT ON FUNCTION handle_stale_tasks IS 'Finds tasks stuck in processing, logs errors, resets to pending. Call via pg_cron or n8n schedule.';
COMMENT ON FUNCTION auto_resolve_errors IS 'Auto-resolves error_logs when matching task_queue entry changes to done.';
