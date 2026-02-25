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
// BUILD FULL QUEUE (manual trigger for "Проверка полноты")
// ============================================

function buildFullQueue() {
  // 1. Get all competitors with client info
  var competitors = supabaseGet('/rest/v1/competitors?select=competitor_site,client_id,clients(id,client_site)');
  if (!competitors || competitors.length === 0) {
    return { success: false, error: 'No competitors found. Add clients and competitors first.' };
  }

  // 2. Get existing task queue (all statuses to prevent duplicates)
  var existingQueue = [];
  try {
    existingQueue = supabaseGet('/rest/v1/task_queue?select=client_site,period,sites_list');
  } catch (e) {
    // Queue may be empty
  }

  // 3. Build set of existing queue keys
  var existingKeys = {};
  for (var eq = 0; eq < existingQueue.length; eq++) {
    var eKey = existingQueue[eq].client_site + '_' + existingQueue[eq].period + '_' + existingQueue[eq].sites_list;
    existingKeys[eKey] = true;
  }

  // 4. Generate last 10 months (skip 2 months lag for SimilarWeb)
  var months = [];
  var now = new Date();
  for (var i = 3; i <= 12; i++) {
    var d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    months.push(y + '.' + m);
  }

  // 5. Group competitors by client
  var clientMap = {}; // clientSite -> { clientId, competitors[] }
  for (var c = 0; c < competitors.length; c++) {
    var row = competitors[c];
    var clientSite = normalizeDomain_(row.clients ? row.clients.client_site : '');
    var clientId = row.clients ? row.clients.id : row.client_id;
    var compSite = normalizeDomain_(row.competitor_site);
    if (!clientSite || !compSite) continue;

    if (!clientMap[clientSite]) {
      clientMap[clientSite] = { clientId: clientId, competitors: [] };
    }
    if (clientMap[clientSite].competitors.indexOf(compSite) === -1) {
      clientMap[clientSite].competitors.push(compSite);
    }
  }

  // 6. Create tasks: chunk competitors into groups of 4 (+1 client = 5 max per SimilarWeb request)
  var MAX_COMPETITORS_PER_CHUNK = 4;
  var tasks = [];

  for (var clientSite in clientMap) {
    var info = clientMap[clientSite];
    var compList = info.competitors;

    // Chunk competitors
    var chunks = [];
    for (var ci = 0; ci < compList.length; ci += MAX_COMPETITORS_PER_CHUNK) {
      chunks.push(compList.slice(ci, ci + MAX_COMPETITORS_PER_CHUNK));
    }

    for (var chunkIdx = 0; chunkIdx < chunks.length; chunkIdx++) {
      var sitesInRequest = [clientSite].concat(chunks[chunkIdx]);
      var sitesList = sitesInRequest.join(',');

      for (var pi = 0; pi < months.length; pi++) {
        var period = months[pi];

        // Check for duplicates
        var qKey = clientSite + '_' + period + '_' + sitesList;
        if (existingKeys[qKey]) continue;

        var queueId = clientSite + '_' + period + '_chunk' + chunkIdx + '_' + Date.now();

        tasks.push({
          queue_id: queueId,
          client_id: info.clientId,
          client_site: clientSite,
          sites_list: sitesList,
          chunk_index: chunkIdx,
          total_chunks: chunks.length,
          period: period,
          status: 'pending',
          priority: pi
        });
      }
    }
  }

  if (tasks.length === 0) {
    return { success: true, tasksCreated: 0, message: 'All data is up to date. No new tasks needed.' };
  }

  // 7. Insert tasks in batches (Supabase has payload limits)
  var BATCH_SIZE = 50;
  for (var bi = 0; bi < tasks.length; bi += BATCH_SIZE) {
    var batch = tasks.slice(bi, bi + BATCH_SIZE);
    supabasePost('/rest/v1/task_queue', batch, { 'Prefer': 'return=minimal,resolution=ignore-duplicates' });
  }

  return {
    success: true,
    tasksCreated: tasks.length,
    clients: Object.keys(clientMap).length,
    periods: months.length,
    message: 'Created ' + tasks.length + ' tasks for ' + Object.keys(clientMap).length + ' clients'
  };
}

function normalizeDomain_(url) {
  if (!url) return '';
  return url
    .replace(/^https?:\/\//i, '')
    .replace(/^www\./i, '')
    .replace(/\/+$/, '')
    .toLowerCase()
    .trim();
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
