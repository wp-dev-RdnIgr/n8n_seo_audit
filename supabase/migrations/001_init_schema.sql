-- =============================================
-- SEO Audit: Supabase Database Schema
-- Migration 001: Initial Schema
-- Project: Comparing SimilarWeb + SEO Audit
-- =============================================

-- =============================================
-- 1. КЛИЕНТЫ
-- =============================================
CREATE TABLE IF NOT EXISTS clients (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_site VARCHAR(255) NOT NULL UNIQUE,
    employee_email VARCHAR(255),
    client_status VARCHAR(50) DEFAULT 'active',
    folder_id VARCHAR(255),
    spreadsheet_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE clients IS 'Клиенты и их настройки';
COMMENT ON COLUMN clients.client_site IS 'Домен сайта клиента (нормализованный, без https/www)';
COMMENT ON COLUMN clients.folder_id IS 'Google Drive folder ID (legacy)';
COMMENT ON COLUMN clients.spreadsheet_id IS 'Google Sheets ID (legacy, для миграции)';

-- =============================================
-- 2. КОНКУРЕНТЫ
-- =============================================
CREATE TABLE IF NOT EXISTS competitors (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    competitor_site VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(client_id, competitor_site)
);

COMMENT ON TABLE competitors IS 'Связки клиент-конкурент для сравнения в SimilarWeb';

-- =============================================
-- 3. МЕТРИКИ SIMILARWEB (основная таблица данных)
-- =============================================
CREATE TABLE IF NOT EXISTS similarweb_data (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    site VARCHAR(255) NOT NULL,
    site_type VARCHAR(20) NOT NULL CHECK (site_type IN ('client', 'competitor')),
    period VARCHAR(7) NOT NULL,

    -- Engagement (Performance Robot)
    monthly_visits VARCHAR(50),
    unique_visitors VARCHAR(50),
    visit_duration VARCHAR(50),
    pages_per_visit VARCHAR(50),
    bounce_rate VARCHAR(50),
    visits_per_visitor VARCHAR(50),
    deduplicated_audience VARCHAR(50),
    page_views VARCHAR(50),

    -- Marketing Channels (Marketing Channels Robot)
    direct VARCHAR(50),
    organic_search VARCHAR(50),
    paid_search VARCHAR(50),
    display_ads VARCHAR(50),
    social VARCHAR(50),
    email VARCHAR(50),

    -- AI Traffic (AI Traffic Robot)
    ai_traffic VARCHAR(50),

    -- Мета
    collected_at DATE DEFAULT CURRENT_DATE,
    task_id VARCHAR(255),
    queue_id VARCHAR(255),

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Upsert-ключ: один site за один period у одного клиента
    UNIQUE(client_id, site, period)
);

COMMENT ON TABLE similarweb_data IS 'Метрики SimilarWeb: engagement, каналы, AI traffic';
COMMENT ON COLUMN similarweb_data.period IS 'Период в формате YYYY.MM (например 2025.01)';
COMMENT ON COLUMN similarweb_data.site_type IS 'client или competitor';

-- =============================================
-- 4. ОЧЕРЕДЬ ЗАДАЧ
-- =============================================
CREATE TABLE IF NOT EXISTS task_queue (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    queue_id VARCHAR(255) NOT NULL UNIQUE,
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    client_site VARCHAR(255) NOT NULL,
    sites_list TEXT NOT NULL,
    chunk_index INT DEFAULT 0,
    total_chunks INT DEFAULT 1,
    period VARCHAR(7) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'done', 'error')),
    priority INT DEFAULT 0,
    task_id VARCHAR(255),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE task_queue IS 'Очередь задач для Browse AI роботов';

-- =============================================
-- 5. ЛОГИ ОШИБОК
-- =============================================
CREATE TABLE IF NOT EXISTS error_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    task_id VARCHAR(255),
    robot_type VARCHAR(50),
    period VARCHAR(7),
    sites TEXT,
    status VARCHAR(50),
    error_message TEXT,
    url TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE error_logs IS 'Логи ошибок Browse AI роботов';

-- =============================================
-- ИНДЕКСЫ
-- =============================================
CREATE INDEX IF NOT EXISTS idx_similarweb_data_client ON similarweb_data(client_id);
CREATE INDEX IF NOT EXISTS idx_similarweb_data_period ON similarweb_data(period);
CREATE INDEX IF NOT EXISTS idx_similarweb_data_site ON similarweb_data(site);
CREATE INDEX IF NOT EXISTS idx_similarweb_data_lookup ON similarweb_data(client_id, site, period);

CREATE INDEX IF NOT EXISTS idx_task_queue_status ON task_queue(status);
CREATE INDEX IF NOT EXISTS idx_task_queue_client ON task_queue(client_id);
CREATE INDEX IF NOT EXISTS idx_task_queue_period ON task_queue(period);

CREATE INDEX IF NOT EXISTS idx_competitors_client ON competitors(client_id);

CREATE INDEX IF NOT EXISTS idx_error_logs_created ON error_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_error_logs_robot_type ON error_logs(robot_type);

-- =============================================
-- ТРИГГЕР: автообновление updated_at
-- =============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_clients_updated
    BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_similarweb_data_updated
    BEFORE UPDATE ON similarweb_data
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_task_queue_updated
    BEFORE UPDATE ON task_queue
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================
-- RLS (Row Level Security) — базовая настройка
-- Включаем RLS, но разрешаем доступ через service_role
-- =============================================
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE competitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE similarweb_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE error_logs ENABLE ROW LEVEL SECURITY;

-- Политики для service_role (n8n будет подключаться через service_role key)
CREATE POLICY "Service role full access" ON clients
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access" ON competitors
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access" ON similarweb_data
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access" ON task_queue
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access" ON error_logs
    FOR ALL USING (true) WITH CHECK (true);

-- =============================================
-- RPC: MERGE-UPSERT для SimilarWeb данных
-- 3 робота пишут разные поля одной строки,
-- поэтому при конфликте сохраняем непустые значения
-- =============================================
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
    SELECT id INTO v_client_id FROM clients WHERE client_site = p_client_site;
    IF v_client_id IS NULL THEN
        RAISE NOTICE 'Client not found: %', p_client_site;
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

COMMENT ON FUNCTION upsert_similarweb_data IS 'Merge-upsert: 3 робота пишут разные поля одной строки, пустые значения не перезатирают существующие';

-- =============================================
-- ГОТОВО!
-- =============================================
