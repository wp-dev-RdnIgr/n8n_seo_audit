// ============================================
// Comparing SimilarWeb — Google Apps Script Backend
// Supabase REST API integration
// ============================================

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('SimilarWeb Comparing')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

// ============================================
// SUPABASE CONFIG (Script Properties)
// ============================================

function getSupabaseConfig() {
  var props = PropertiesService.getScriptProperties();
  return {
    url: props.getProperty('SUPABASE_URL') || '',
    key: props.getProperty('SUPABASE_KEY') || ''
  };
}

function saveSupabaseConfig(url, key) {
  if (!url || !key) return { success: false, error: 'URL and Key are required' };
  var props = PropertiesService.getScriptProperties();
  props.setProperty('SUPABASE_URL', url.replace(/\/$/, ''));
  props.setProperty('SUPABASE_KEY', key);
  return { success: true };
}

function testSupabaseConnection() {
  var config = getSupabaseConfig();
  if (!config.url || !config.key) return { success: false, error: 'URL and Key not configured' };

  try {
    // Step 1: test basic connectivity via REST root
    var options = {
      method: 'get',
      headers: {
        'apikey': config.key,
        'Authorization': 'Bearer ' + config.key
      },
      muteHttpExceptions: true
    };

    var resp = UrlFetchApp.fetch(config.url + '/rest/v1/', options);
    var code = resp.getResponseCode();

    if (code === 404) {
      return { success: false, error: 'URL wrong or REST API not available. URL: ' + config.url };
    }

    // Step 2: try to read clients table
    var resp2 = UrlFetchApp.fetch(config.url + '/rest/v1/clients?select=id&limit=1', options);
    var code2 = resp2.getResponseCode();
    var text2 = resp2.getContentText();

    if (code2 >= 400) {
      // Possibly schema cache needs reload
      // Try to notify PostgREST to reload via /rest/v1/rpc endpoint
      return {
        success: false,
        error: 'Tables not visible (HTTP ' + code2 + '). Go to Supabase Dashboard → Settings → API → click "Reload schema cache". Then try again. Details: ' + text2.substring(0, 200)
      };
    }

    return { success: true, message: 'Connected! Found clients table. Response code: ' + code2 };
  } catch (e) {
    return { success: false, error: e.toString() };
  }
}

// ============================================
// SUPABASE HTTP HELPERS
// ============================================

function supabaseRequest_(method, path, body, extraHeaders) {
  var config = getSupabaseConfig();
  if (!config.url || !config.key) throw new Error('Supabase not configured. Go to Settings tab.');

  var options = {
    method: method,
    headers: {
      'apikey': config.key,
      'Authorization': 'Bearer ' + config.key,
      'Content-Type': 'application/json',
      'Prefer': 'return=representation'
    },
    muteHttpExceptions: true
  };

  if (extraHeaders) {
    for (var h in extraHeaders) options.headers[h] = extraHeaders[h];
  }

  if (body && (method === 'post' || method === 'patch')) {
    options.payload = JSON.stringify(body);
  }

  var resp = UrlFetchApp.fetch(config.url + path, options);
  var code = resp.getResponseCode();
  var text = resp.getContentText();

  if (code >= 400) {
    throw new Error('Supabase ' + code + ': ' + text);
  }

  return text ? JSON.parse(text) : null;
}

function supabaseGet(path) { return supabaseRequest_('get', path); }
function supabasePost(path, body, headers) { return supabaseRequest_('post', path, body, headers); }
function supabasePatch(path, body) { return supabaseRequest_('patch', path, body); }
function supabaseDelete(path) { return supabaseRequest_('delete', path); }

// ============================================
// CLIENTS
// ============================================

function getClients() {
  return supabaseGet('/rest/v1/clients?select=*&order=client_site.asc');
}

function addClient(clientSite, employeeEmail) {
  var site = clientSite.replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/.*$/, '').toLowerCase().trim();
  if (!site || !site.includes('.')) return { success: false, error: 'Invalid domain' };
  var result = supabasePost('/rest/v1/clients', {
    client_site: site,
    employee_email: employeeEmail || null,
    client_status: 'active'
  }, { 'Prefer': 'return=representation,resolution=merge-duplicates' });
  return { success: true, data: result };
}

function updateClient(id, data) {
  var result = supabasePatch('/rest/v1/clients?id=eq.' + id, data);
  return { success: true, data: result };
}

function deleteClient(id) {
  supabaseDelete('/rest/v1/competitors?client_id=eq.' + id);
  supabaseDelete('/rest/v1/clients?id=eq.' + id);
  return { success: true };
}

// ============================================
// COMPETITORS
// ============================================

function getCompetitors(clientId) {
  return supabaseGet('/rest/v1/competitors?client_id=eq.' + clientId + '&select=*&order=competitor_site.asc');
}

function getAllCompetitorsWithClients() {
  return supabaseGet('/rest/v1/competitors?select=id,competitor_site,client_id,clients(client_site)&order=competitor_site.asc');
}

function addCompetitor(clientId, competitorSite) {
  var site = competitorSite.replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/.*$/, '').toLowerCase().trim();
  if (!site || !site.includes('.')) return { success: false, error: 'Invalid domain' };
  var result = supabasePost('/rest/v1/competitors', {
    client_id: clientId,
    competitor_site: site
  });
  return { success: true, data: result };
}

function deleteCompetitor(id) {
  supabaseDelete('/rest/v1/competitors?id=eq.' + id);
  return { success: true };
}

// ============================================
// SIMILARWEB DATA
// ============================================

function getSimilarwebData(clientId, period) {
  var path = '/rest/v1/similarweb_data?client_id=eq.' + clientId + '&select=*&order=site_type.asc,site.asc';
  if (period) path += '&period=eq.' + period;
  return supabaseGet(path);
}

function getAvailablePeriods() {
  return supabaseGet('/rest/v1/similarweb_data?select=period&order=period.desc&limit=50');
}

// ============================================
// TASK QUEUE
// ============================================

function getTaskQueue(statusFilter) {
  var path = '/rest/v1/task_queue?select=*&order=created_at.desc&limit=100';
  if (statusFilter && statusFilter !== 'all') path += '&status=eq.' + statusFilter;
  return supabaseGet(path);
}

function createComparisonTasks(clientId, period) {
  // Get client
  var clients = supabaseGet('/rest/v1/clients?id=eq.' + clientId + '&select=*');
  if (!clients || clients.length === 0) return { success: false, error: 'Client not found' };
  var client = clients[0];

  // Get competitors
  var competitors = supabaseGet('/rest/v1/competitors?client_id=eq.' + clientId + '&select=competitor_site');
  if (!competitors || competitors.length === 0) return { success: false, error: 'No competitors configured' };

  // Build site list: client + all competitors
  var sites = [client.client_site];
  for (var i = 0; i < competitors.length; i++) {
    sites.push(competitors[i].competitor_site);
  }

  // Chunk into groups of 5
  var chunkSize = 5;
  var chunks = [];
  for (var j = 0; j < sites.length; j += chunkSize) {
    chunks.push(sites.slice(j, j + chunkSize));
  }

  var tasks = [];
  for (var k = 0; k < chunks.length; k++) {
    tasks.push({
      queue_id: Utilities.getUuid(),
      client_id: clientId,
      client_site: client.client_site,
      sites_list: chunks[k].join(','),
      chunk_index: k,
      total_chunks: chunks.length,
      period: period,
      status: 'pending'
    });
  }

  var result = supabasePost('/rest/v1/task_queue', tasks);
  return { success: true, tasksCreated: tasks.length, data: result };
}

function retryTask(queueId) {
  var result = supabasePatch('/rest/v1/task_queue?queue_id=eq.' + queueId, {
    status: 'pending',
    error_message: null,
    task_id: null
  });
  return { success: true, data: result };
}

function deleteTask(id) {
  supabaseDelete('/rest/v1/task_queue?id=eq.' + id);
  return { success: true };
}

// ============================================
// ERROR LOGS
// ============================================

function getErrorLogs(limit) {
  var lim = limit || 50;
  return supabaseGet('/rest/v1/error_logs?select=*&order=created_at.desc&limit=' + lim);
}

// ============================================
// DASHBOARD STATS
// ============================================

function getDashboardStats() {
  var clients = supabaseGet('/rest/v1/clients?select=id');
  var competitors = supabaseGet('/rest/v1/competitors?select=id');
  var pendingTasks = supabaseGet('/rest/v1/task_queue?status=eq.pending&select=id');
  var doneTasks = supabaseGet('/rest/v1/task_queue?status=eq.done&select=id');
  var errors = supabaseGet('/rest/v1/error_logs?select=id&order=created_at.desc&limit=100');
  var dataRows = supabaseGet('/rest/v1/similarweb_data?select=id&limit=1000');

  return {
    totalClients: clients ? clients.length : 0,
    totalCompetitors: competitors ? competitors.length : 0,
    pendingTasks: pendingTasks ? pendingTasks.length : 0,
    completedTasks: doneTasks ? doneTasks.length : 0,
    recentErrors: errors ? errors.length : 0,
    dataRows: dataRows ? dataRows.length : 0
  };
}
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
