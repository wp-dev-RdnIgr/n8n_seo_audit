/**
 * SEO Audit — Web Interface
 * Server-side: Supabase REST API wrapper
 *
 * Script Properties (set in Project Settings > Script Properties):
 *   SUPABASE_URL  — https://utvoegofnctfwrjdxjvf.supabase.co
 *   SUPABASE_KEY  — service_role key
 */

// ─── Config ────────────────────────────────────────────

function getConfig_() {
  const props = PropertiesService.getScriptProperties();
  return {
    url: props.getProperty('SUPABASE_URL') || '',
    key: props.getProperty('SUPABASE_KEY') || ''
  };
}

// ─── Web App Entry ─────────────────────────────────────

function doGet() {
  return HtmlService
    .createTemplateFromFile('Index')
    .evaluate()
    .setTitle('SEO Audit — SimilarWeb')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/** Include helper for HTML templates */
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

// ─── Supabase helpers ──────────────────────────────────

function supabaseRequest_(method, path, body, extraHeaders) {
  const cfg = getConfig_();
  if (!cfg.url || !cfg.key) throw new Error('Supabase credentials not configured');

  const options = {
    method: method,
    headers: {
      'apikey': cfg.key,
      'Authorization': 'Bearer ' + cfg.key,
      'Content-Type': 'application/json',
      'Prefer': 'return=representation',
      ...extraHeaders
    },
    muteHttpExceptions: true
  };
  if (body && (method === 'post' || method === 'patch' || method === 'put')) {
    options.payload = JSON.stringify(body);
  }

  const resp = UrlFetchApp.fetch(cfg.url + '/rest/v1/' + path, options);
  const code = resp.getResponseCode();
  const text = resp.getContentText();

  if (code >= 400) throw new Error('Supabase ' + code + ': ' + text);
  if (!text) return [];
  return JSON.parse(text);
}

// ─── Clients CRUD ──────────────────────────────────────

function getClients() {
  return supabaseRequest_('get', 'clients?select=*&order=client_site');
}

function addClient(clientSite) {
  const site = clientSite.toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/+$/, '').trim();
  if (!site) throw new Error('Empty site');
  return supabaseRequest_('post', 'clients', { client_site: site });
}

function deleteClient(clientId) {
  return supabaseRequest_('delete', 'clients?id=eq.' + clientId);
}

// ─── Competitors CRUD ──────────────────────────────────

function getCompetitors(clientId) {
  return supabaseRequest_('get', 'competitors?client_id=eq.' + clientId + '&select=*&order=competitor_site');
}

function getAllCompetitors() {
  return supabaseRequest_('get', 'competitors?select=id,competitor_site,client_id,clients(client_site)&order=competitor_site');
}

function addCompetitor(clientId, competitorSite) {
  const site = competitorSite.toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/+$/, '').trim();
  if (!site) throw new Error('Empty site');
  return supabaseRequest_('post', 'competitors', { client_id: clientId, competitor_site: site });
}

function deleteCompetitor(competitorId) {
  return supabaseRequest_('delete', 'competitors?id=eq.' + competitorId);
}

// ─── SimilarWeb Data ───────────────────────────────────

function getDataForClient(clientId) {
  return supabaseRequest_('get',
    'similarweb_data?client_id=eq.' + clientId +
    '&select=*&order=period.desc,site_type,site'
  );
}

function getDataForPeriod(clientId, period) {
  return supabaseRequest_('get',
    'similarweb_data?client_id=eq.' + clientId +
    '&period=eq.' + period +
    '&select=*&order=site_type,site'
  );
}

function getAvailablePeriods(clientId) {
  const data = supabaseRequest_('get',
    'similarweb_data?client_id=eq.' + clientId +
    '&select=period&order=period.desc'
  );
  const unique = [...new Set(data.map(r => r.period))];
  return unique;
}

// ─── Queue Status ──────────────────────────────────────

function getQueueStatus() {
  return supabaseRequest_('get',
    'task_queue?select=*&order=created_at.desc&limit=50'
  );
}

function getQueueSummary() {
  const all = supabaseRequest_('get', 'task_queue?select=status');
  const summary = { pending: 0, processing: 0, done: 0, error: 0, total: all.length };
  all.forEach(r => { if (summary[r.status] !== undefined) summary[r.status]++; });
  return summary;
}

// ─── Error Logs ────────────────────────────────────────

function getRecentErrors() {
  return supabaseRequest_('get',
    'error_logs?select=*&order=created_at.desc&limit=20'
  );
}

// ─── Settings check ────────────────────────────────────

function checkConnection() {
  try {
    const clients = getClients();
    return { ok: true, clientCount: clients.length };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

function saveSettings(url, key) {
  const props = PropertiesService.getScriptProperties();
  props.setProperty('SUPABASE_URL', url.replace(/\/+$/, ''));
  props.setProperty('SUPABASE_KEY', key);
  return checkConnection();
}

function getSettings() {
  const cfg = getConfig_();
  return { url: cfg.url, hasKey: !!cfg.key };
}
