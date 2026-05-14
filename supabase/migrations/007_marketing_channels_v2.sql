-- =============================================
-- 007: Marketing Channels v2
-- Що:
--   - дроп старої колонки `social` (дані будуть зібрані заново через окремі Organic/Paid)
--   - нові колонки: social_organic, social_paid, affiliates, gen_ai
--   - оновлена функція upsert_similarweb_data (нова сигнатура без p_social, з 4 новими параметрами)
-- =============================================

-- Старая функция использует параметр p_social и пишет в колонку social — её надо снести
-- перед DROP COLUMN, иначе будет ошибка зависимости.
DROP FUNCTION IF EXISTS upsert_similarweb_data(
    TEXT, TEXT, TEXT, TEXT,
    TEXT, TEXT, TEXT, TEXT, TEXT,
    TEXT, TEXT, TEXT,
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT,
    TEXT,
    TEXT, TEXT, DATE
);

-- Дроп старої колонки social
ALTER TABLE similarweb_data DROP COLUMN IF EXISTS social;

-- Нові колонки
ALTER TABLE similarweb_data
    ADD COLUMN IF NOT EXISTS social_organic VARCHAR(50),
    ADD COLUMN IF NOT EXISTS social_paid    VARCHAR(50),
    ADD COLUMN IF NOT EXISTS affiliates     VARCHAR(50),
    ADD COLUMN IF NOT EXISTS gen_ai         VARCHAR(50);

COMMENT ON COLUMN similarweb_data.social_organic IS 'Social - Organic (Marketing Channels Robot)';
COMMENT ON COLUMN similarweb_data.social_paid    IS 'Social - Paid (Marketing Channels Robot)';
COMMENT ON COLUMN similarweb_data.affiliates     IS 'Affiliates (Marketing Channels Robot)';
COMMENT ON COLUMN similarweb_data.gen_ai         IS 'Gen AI з Channel Traffic — місячне значення (Marketing Channels Robot)';
COMMENT ON COLUMN similarweb_data.ai_traffic     IS 'Avg AI Traffic per Domain з /ai-traffic — середнє за період (AI Traffic Robot)';

-- =============================================
-- Нова функція upsert_similarweb_data
-- Зміни порівняно з v1:
--   - прибрано p_social
--   - додано p_social_organic, p_social_paid, p_affiliates, p_gen_ai
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
    p_social_organic TEXT DEFAULT NULL,
    p_social_paid TEXT DEFAULT NULL,
    p_email TEXT DEFAULT NULL,
    p_affiliates TEXT DEFAULT NULL,
    p_gen_ai TEXT DEFAULT NULL,
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
        direct, organic_search, paid_search, display_ads,
        social_organic, social_paid, email, affiliates, gen_ai,
        ai_traffic, task_id, queue_id, collected_at
    ) VALUES (
        v_client_id, p_site, p_site_type, p_period,
        p_monthly_visits, p_unique_visitors, p_visit_duration, p_pages_per_visit, p_bounce_rate,
        p_visits_per_visitor, p_deduplicated_audience, p_page_views,
        p_direct, p_organic_search, p_paid_search, p_display_ads,
        p_social_organic, p_social_paid, p_email, p_affiliates, p_gen_ai,
        p_ai_traffic, p_task_id, p_queue_id, p_collected_at
    )
    ON CONFLICT (client_id, site, period) DO UPDATE SET
        site_type             = COALESCE(NULLIF(EXCLUDED.site_type, ''), similarweb_data.site_type),
        monthly_visits        = COALESCE(NULLIF(EXCLUDED.monthly_visits, ''), similarweb_data.monthly_visits),
        unique_visitors       = COALESCE(NULLIF(EXCLUDED.unique_visitors, ''), similarweb_data.unique_visitors),
        visit_duration        = COALESCE(NULLIF(EXCLUDED.visit_duration, ''), similarweb_data.visit_duration),
        pages_per_visit       = COALESCE(NULLIF(EXCLUDED.pages_per_visit, ''), similarweb_data.pages_per_visit),
        bounce_rate           = COALESCE(NULLIF(EXCLUDED.bounce_rate, ''), similarweb_data.bounce_rate),
        visits_per_visitor    = COALESCE(NULLIF(EXCLUDED.visits_per_visitor, ''), similarweb_data.visits_per_visitor),
        deduplicated_audience = COALESCE(NULLIF(EXCLUDED.deduplicated_audience, ''), similarweb_data.deduplicated_audience),
        page_views            = COALESCE(NULLIF(EXCLUDED.page_views, ''), similarweb_data.page_views),
        direct                = COALESCE(NULLIF(EXCLUDED.direct, ''), similarweb_data.direct),
        organic_search        = COALESCE(NULLIF(EXCLUDED.organic_search, ''), similarweb_data.organic_search),
        paid_search           = COALESCE(NULLIF(EXCLUDED.paid_search, ''), similarweb_data.paid_search),
        display_ads           = COALESCE(NULLIF(EXCLUDED.display_ads, ''), similarweb_data.display_ads),
        social_organic        = COALESCE(NULLIF(EXCLUDED.social_organic, ''), similarweb_data.social_organic),
        social_paid           = COALESCE(NULLIF(EXCLUDED.social_paid, ''), similarweb_data.social_paid),
        email                 = COALESCE(NULLIF(EXCLUDED.email, ''), similarweb_data.email),
        affiliates            = COALESCE(NULLIF(EXCLUDED.affiliates, ''), similarweb_data.affiliates),
        gen_ai                = COALESCE(NULLIF(EXCLUDED.gen_ai, ''), similarweb_data.gen_ai),
        ai_traffic            = COALESCE(NULLIF(EXCLUDED.ai_traffic, ''), similarweb_data.ai_traffic),
        task_id               = COALESCE(NULLIF(EXCLUDED.task_id, ''), similarweb_data.task_id),
        queue_id              = COALESCE(NULLIF(EXCLUDED.queue_id, ''), similarweb_data.queue_id),
        collected_at          = COALESCE(EXCLUDED.collected_at, similarweb_data.collected_at),
        updated_at            = now();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION upsert_similarweb_data IS 'Merge-upsert v2: 3 робота пишут разные поля одной строки. Social расщеплён на organic/paid. Добавлены affiliates и gen_ai.';

-- =============================================
-- ГОТОВО!
-- =============================================
