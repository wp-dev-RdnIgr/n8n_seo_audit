-- ============================================
-- Migration 003: Dashboard Stats RPC + Performance Optimizations
-- Replaces 7 sequential API calls with 1 RPC call
-- ============================================

-- Single RPC function for all dashboard statistics
CREATE OR REPLACE FUNCTION get_dashboard_stats()
RETURNS JSON
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  result JSON;
BEGIN
  SELECT json_build_object(
    'totalClients', (SELECT COUNT(*) FROM clients),
    'totalCompetitors', (SELECT COUNT(*) FROM competitors),
    'pendingTasks', (SELECT COUNT(*) FROM task_queue WHERE status = 'pending'),
    'completedTasks', (SELECT COUNT(*) FROM task_queue WHERE status = 'done'),
    'unresolvedErrors', (SELECT COUNT(*) FROM error_logs WHERE resolved = FALSE),
    'recentErrors', (SELECT COUNT(*) FROM error_logs),
    'dataRows', (SELECT COUNT(*) FROM similarweb_data)
  ) INTO result;

  RETURN result;
END;
$$;

-- Optimized function to get distinct periods (avoids transferring full rows)
CREATE OR REPLACE FUNCTION get_distinct_periods()
RETURNS TABLE(period VARCHAR)
LANGUAGE sql
STABLE
AS $$
  SELECT DISTINCT sd.period
  FROM similarweb_data sd
  ORDER BY sd.period DESC;
$$;

-- Index for faster COUNT on task_queue by status
CREATE INDEX IF NOT EXISTS idx_task_queue_status ON task_queue(status);

-- Composite index for similarweb_data lookups
CREATE INDEX IF NOT EXISTS idx_similarweb_data_client_period ON similarweb_data(client_id, period);
