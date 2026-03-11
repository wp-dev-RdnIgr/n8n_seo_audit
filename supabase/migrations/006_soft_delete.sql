-- ============================================
-- Migration 006: Soft Delete for clients and competitors
-- Instead of physically deleting records, we set deleted_at timestamp.
-- All queries filter out records where deleted_at IS NOT NULL.
-- ============================================

-- 1. Add deleted_at column to clients
ALTER TABLE clients ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;

-- 2. Add deleted_at column to competitors
ALTER TABLE competitors ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;

-- 3. Index for fast filtering of non-deleted records
CREATE INDEX IF NOT EXISTS idx_clients_deleted_at ON clients(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_competitors_deleted_at ON competitors(deleted_at) WHERE deleted_at IS NULL;

-- 4. Update get_dashboard_stats to exclude soft-deleted records
CREATE OR REPLACE FUNCTION get_dashboard_stats()
RETURNS JSON
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  result JSON;
BEGIN
  SELECT json_build_object(
    'totalClients', (SELECT COUNT(*) FROM clients WHERE deleted_at IS NULL),
    'totalCompetitors', (SELECT COUNT(*) FROM competitors WHERE deleted_at IS NULL),
    'pendingTasks', (SELECT COUNT(*) FROM task_queue WHERE status = 'pending'),
    'completedTasks', (SELECT COUNT(*) FROM task_queue WHERE status = 'done'),
    'unresolvedErrors', (SELECT COUNT(*) FROM error_logs WHERE resolved = FALSE),
    'recentErrors', (SELECT COUNT(*) FROM error_logs),
    'dataRows', (SELECT COUNT(*) FROM similarweb_data)
  ) INTO result;

  RETURN result;
END;
$$;

-- 5. Update upsert_similarweb_data to skip soft-deleted clients
CREATE OR REPLACE FUNCTION upsert_similarweb_data(
    p_client_site TEXT,
    p_site TEXT,
    p_site_type TEXT,
    p_period TEXT,
    p_monthly_visits TEXT DEFAULT NULL,
    p_unique_visitors TEXT DEFAULT NULL,
    p_visit_duration TEXT DEFAULT NULL,
    p_pages_per_visit TEXT DEFAULT NULL,
    p_bounce_rate TEXT DEFAULT NULL,
    p_visits_per_visitor TEXT DEFAULT NULL,
    p_deduplicated_audience TEXT DEFAULT NULL,
    p_page_views TEXT DEFAULT NULL,
    p_direct TEXT DEFAULT NULL,
    p_organic_search TEXT DEFAULT NULL,
    p_paid_search TEXT DEFAULT NULL,
    p_display_ads TEXT DEFAULT NULL,
    p_social TEXT DEFAULT NULL,
    p_email TEXT DEFAULT NULL,
    p_ai_traffic TEXT DEFAULT NULL,
    p_task_id TEXT DEFAULT NULL,
    p_queue_id TEXT DEFAULT NULL,
    p_collected_at DATE DEFAULT CURRENT_DATE
) RETURNS void AS $$
DECLARE
    v_client_id UUID;
BEGIN
    SELECT id INTO v_client_id FROM clients WHERE client_site = p_client_site AND deleted_at IS NULL;
    IF v_client_id IS NULL THEN
        RAISE NOTICE 'Client not found or deleted: %', p_client_site;
        RETURN;
    END IF;

    INSERT INTO similarweb_data (
        client_id, site, site_type, period,
        monthly_visits, unique_visitors, visit_duration, pages_per_visit, bounce_rate,
        visits_per_visitor, deduplicated_audience, page_views,
        direct, organic_search, paid_search, display_ads, social, email,
        ai_traffic, task_id, queue_id, collected_at
    ) VALUES (
        v_client_id, p_site, p_site_type, p_period,
        p_monthly_visits, p_unique_visitors, p_visit_duration, p_pages_per_visit, p_bounce_rate,
        p_visits_per_visitor, p_deduplicated_audience, p_page_views,
        p_direct, p_organic_search, p_paid_search, p_display_ads, p_social, p_email,
        p_ai_traffic, p_task_id, p_queue_id, p_collected_at
    )
    ON CONFLICT (client_id, site, period) DO UPDATE SET
        site_type       = COALESCE(NULLIF(EXCLUDED.site_type, ''), similarweb_data.site_type),
        monthly_visits  = COALESCE(NULLIF(EXCLUDED.monthly_visits, ''), similarweb_data.monthly_visits),
        unique_visitors = COALESCE(NULLIF(EXCLUDED.unique_visitors, ''), similarweb_data.unique_visitors),
        visit_duration  = COALESCE(NULLIF(EXCLUDED.visit_duration, ''), similarweb_data.visit_duration),
        pages_per_visit = COALESCE(NULLIF(EXCLUDED.pages_per_visit, ''), similarweb_data.pages_per_visit),
        bounce_rate     = COALESCE(NULLIF(EXCLUDED.bounce_rate, ''), similarweb_data.bounce_rate),
        visits_per_visitor    = COALESCE(NULLIF(EXCLUDED.visits_per_visitor, ''), similarweb_data.visits_per_visitor),
        deduplicated_audience = COALESCE(NULLIF(EXCLUDED.deduplicated_audience, ''), similarweb_data.deduplicated_audience),
        page_views      = COALESCE(NULLIF(EXCLUDED.page_views, ''), similarweb_data.page_views),
        direct          = COALESCE(NULLIF(EXCLUDED.direct, ''), similarweb_data.direct),
        organic_search  = COALESCE(NULLIF(EXCLUDED.organic_search, ''), similarweb_data.organic_search),
        paid_search     = COALESCE(NULLIF(EXCLUDED.paid_search, ''), similarweb_data.paid_search),
        display_ads     = COALESCE(NULLIF(EXCLUDED.display_ads, ''), similarweb_data.display_ads),
        social          = COALESCE(NULLIF(EXCLUDED.social, ''), similarweb_data.social),
        email           = COALESCE(NULLIF(EXCLUDED.email, ''), similarweb_data.email),
        ai_traffic      = COALESCE(NULLIF(EXCLUDED.ai_traffic, ''), similarweb_data.ai_traffic),
        task_id         = COALESCE(NULLIF(EXCLUDED.task_id, ''), similarweb_data.task_id),
        queue_id        = COALESCE(NULLIF(EXCLUDED.queue_id, ''), similarweb_data.queue_id),
        collected_at    = COALESCE(EXCLUDED.collected_at, similarweb_data.collected_at),
        updated_at      = now();
END;
$$ LANGUAGE plpgsql;
