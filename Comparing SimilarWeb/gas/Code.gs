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

function supabaseRpc(fnName, params) {
  return supabaseRequest_('post', '/rest/v1/rpc/' + fnName, params || {});
}

// ============================================
// CLIENTS
// ============================================

function getClients() {
  return supabaseGet('/rest/v1/clients?select=id,client_site,employee_email,client_status,created_at&deleted_at=is.null&order=client_site.asc');
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
  // Soft delete: set deleted_at timestamp instead of removing rows
  var now = new Date().toISOString();
  supabasePatch('/rest/v1/competitors?client_id=eq.' + id + '&deleted_at=is.null', { deleted_at: now });
  supabasePatch('/rest/v1/clients?id=eq.' + id, { deleted_at: now });
  return { success: true };
}

// ============================================
// COMPETITORS
// ============================================

function getCompetitors(clientId) {
  return supabaseGet('/rest/v1/competitors?client_id=eq.' + clientId + '&deleted_at=is.null&select=*&order=competitor_site.asc');
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
  // Soft delete: set deleted_at timestamp instead of removing row
  supabasePatch('/rest/v1/competitors?id=eq.' + id, { deleted_at: new Date().toISOString() });
  return { success: true };
}

// ============================================
// SIMILARWEB DATA
// ============================================

function getSimilarwebData(clientId, periodFrom, periodTo) {
  // Get active sites (client + non-deleted competitors) to exclude soft-deleted
  var activeSites = getActiveSitesForClient_(clientId);
  if (!activeSites.length) return [];

  var cols = 'id,site,site_type,period,monthly_visits,unique_visitors,visits_per_visitor,deduplicated_audience,page_views,visit_duration,pages_per_visit,bounce_rate,direct,organic_search,paid_search,display_ads,social,email,ai_traffic';
  var path = '/rest/v1/similarweb_data?client_id=eq.' + clientId
    + '&site=in.(' + activeSites.map(encodeURIComponent).join(',') + ')'
    + '&select=' + cols + '&order=period.asc,site_type.asc,site.asc';
  if (periodFrom && periodTo) {
    path += '&period=gte.' + periodFrom + '&period=lte.' + periodTo;
  } else if (periodFrom) {
    path += '&period=eq.' + periodFrom;
  }
  return supabaseGet(path);
}

// Helper: returns array of active site domains for a client (client_site + non-deleted competitor_sites)
function getActiveSitesForClient_(clientId) {
  var clients = supabaseGet('/rest/v1/clients?id=eq.' + clientId + '&select=client_site');
  var competitors = supabaseGet('/rest/v1/competitors?client_id=eq.' + clientId + '&deleted_at=is.null&select=competitor_site');
  var sites = [];
  if (clients && clients.length) sites.push(clients[0].client_site);
  if (competitors) {
    for (var i = 0; i < competitors.length; i++) sites.push(competitors[i].competitor_site);
  }
  return sites;
}

function getAvailablePeriods() {
  return supabaseRpc('get_distinct_periods');
}

function getClientPeriods(clientId) {
  return supabaseRpc('get_client_periods', { p_client_id: clientId });
}

// ============================================
// TASK QUEUE
// ============================================

function getTaskQueue(statusFilter) {
  var path = '/rest/v1/task_queue?select=id,queue_id,client_site,sites_list,period,chunk_index,total_chunks,status,error_message,created_at&order=created_at.desc&limit=100';
  if (statusFilter && statusFilter !== 'all') path += '&status=eq.' + statusFilter;
  return supabaseGet(path);
}

function createComparisonTasks(clientId, period) {
  // Get client
  var clients = supabaseGet('/rest/v1/clients?id=eq.' + clientId + '&select=*');
  if (!clients || clients.length === 0) return { success: false, error: 'Client not found' };
  var client = clients[0];

  // Get competitors (exclude soft-deleted)
  var competitors = supabaseGet('/rest/v1/competitors?client_id=eq.' + clientId + '&deleted_at=is.null&select=competitor_site');
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

function getErrorLogs(limit, filter) {
  var lim = limit || 50;
  var path = '/rest/v1/error_logs?select=id,robot_type,period,sites,error_message,resolved,resolved_at,retry_count,queue_id,created_at&order=created_at.desc&limit=' + lim;
  if (filter === 'unresolved') path += '&resolved=eq.false';
  if (filter === 'resolved') path += '&resolved=eq.true';
  return supabaseGet(path);
}

function resolveError(errorId) {
  var result = supabasePatch('/rest/v1/error_logs?id=eq.' + errorId, {
    resolved: true,
    resolved_at: new Date().toISOString()
  });
  return { success: true, data: result };
}

function retryError(errorId) {
  // Get the error record
  var errors = supabaseGet('/rest/v1/error_logs?id=eq.' + errorId + '&select=*');
  if (!errors || errors.length === 0) return { success: false, error: 'Error not found' };
  var err = errors[0];

  // Find matching task in queue by queue_id
  if (err.queue_id) {
    var tasks = supabaseGet('/rest/v1/task_queue?queue_id=eq.' + err.queue_id + '&select=*');
    if (tasks && tasks.length > 0) {
      // Reset the task to pending
      supabasePatch('/rest/v1/task_queue?queue_id=eq.' + err.queue_id, {
        status: 'pending',
        task_id: null,
        error_message: 'Manual retry from error log #' + errorId
      });
      // Increment retry count
      supabasePatch('/rest/v1/error_logs?id=eq.' + errorId, {
        retry_count: (err.retry_count || 0) + 1
      });
      return { success: true, message: 'Task reset to pending for retry' };
    }
  }

  // No queue_id or task not found — try to find task by period + sites
  if (err.period && err.sites) {
    var sitesMatch = encodeURIComponent(err.sites);
    var matchTasks = supabaseGet('/rest/v1/task_queue?period=eq.' + err.period + '&sites_list=eq.' + sitesMatch + '&select=*&limit=1');
    if (matchTasks && matchTasks.length > 0) {
      supabasePatch('/rest/v1/task_queue?id=eq.' + matchTasks[0].id, {
        status: 'pending',
        task_id: null,
        error_message: 'Manual retry from error log'
      });
      supabasePatch('/rest/v1/error_logs?id=eq.' + errorId, {
        retry_count: (err.retry_count || 0) + 1
      });
      return { success: true, message: 'Task reset to pending for retry' };
    }
  }

  return { success: false, error: 'Could not find matching task in queue. The task may need to be recreated manually.' };
}

// ============================================
// BUILD FULL QUEUE (triggers n8n "Проверка полноты" webhook)
// ============================================

var N8N_QUEUE_BUILD_WEBHOOK = 'https://n8n.rnd.webpromo.tools/webhook/27adbc76-58fa-4b6e-a6ea-3b6516c65712';

function buildFullQueue() {
  try {
    var resp = UrlFetchApp.fetch(N8N_QUEUE_BUILD_WEBHOOK, {
      method: 'get',
      muteHttpExceptions: true
    });

    var code = resp.getResponseCode();
    var body = resp.getContentText();

    if (code >= 200 && code < 300) {
      return { success: true, message: 'Queue build triggered in n8n. Check Task Queue tab for results.' };
    } else {
      return { success: false, error: 'n8n returned HTTP ' + code + ': ' + body.substring(0, 200) };
    }
  } catch (e) {
    return { success: false, error: 'Failed to reach n8n: ' + e.toString() };
  }
}

// ============================================
// DASHBOARD STATS
// ============================================

function getDashboardStats() {
  return supabaseRpc('get_dashboard_stats');
}

// ============================================
// REVIEW PAGE
// ============================================

function getClientReviewData(clientId, periodFrom, periodTo) {
  // Get all similarweb_data for client + active (non-deleted) competitors in date range
  var activeSites = getActiveSitesForClient_(clientId);
  if (!activeSites.length) return [];

  var cols = 'id,site,site_type,period,monthly_visits,unique_visitors,visits_per_visitor,deduplicated_audience,page_views,visit_duration,pages_per_visit,bounce_rate,direct,organic_search,paid_search,display_ads,social,email,ai_traffic';
  var path = '/rest/v1/similarweb_data?client_id=eq.' + clientId
    + '&site=in.(' + activeSites.map(encodeURIComponent).join(',') + ')'
    + '&select=' + cols + '&order=period.asc,site_type.asc,site.asc';
  if (periodFrom && periodTo) {
    path += '&period=gte.' + periodFrom + '&period=lte.' + periodTo;
  }
  return supabaseGet(path);
}

function getClientWithCompetitors(clientId) {
  var client = supabaseGet('/rest/v1/clients?id=eq.' + clientId + '&deleted_at=is.null&select=id,client_site,employee_email,client_status');
  var competitors = supabaseGet('/rest/v1/competitors?client_id=eq.' + clientId + '&deleted_at=is.null&select=id,competitor_site&order=competitor_site.asc');
  return {
    client: (client && client.length) ? client[0] : null,
    competitors: competitors || []
  };
}
