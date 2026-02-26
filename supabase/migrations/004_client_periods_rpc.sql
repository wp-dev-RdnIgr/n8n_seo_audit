-- ============================================
-- Migration 004: Client-specific periods RPC
-- Returns only periods that have data for a given client
-- Prevents showing empty periods in dropdown filters
-- ============================================

CREATE OR REPLACE FUNCTION get_client_periods(p_client_id UUID)
RETURNS TABLE(period VARCHAR)
LANGUAGE sql
STABLE
AS $$
  SELECT DISTINCT sd.period
  FROM similarweb_data sd
  WHERE sd.client_id = p_client_id
  ORDER BY sd.period DESC;
$$;
