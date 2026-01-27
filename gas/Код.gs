// ============================================
// РОУТИНГ: ?page=audit | ?page=gkp
// ============================================

function doGet(e) {
  var page = (e && e.parameter && e.parameter.page) ? e.parameter.page : 'audit';

  var pages = {
    'audit': { file: 'form', title: 'Аналіз конкурентів' },
    'gkp':   { file: 'gkp_form', title: 'Семантичне ядро (GKP)' }
  };

  var config = pages[page] || pages['audit'];

  return HtmlService.createHtmlOutputFromFile(config.file)
    .setTitle(config.title)
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

// ============================================
// БЕКЕНД: Аналіз конкурентів
// ============================================

function submitAudit(domain) {
  var cleanDomain = domain
    .replace(/^https?:\/\//, '')
    .replace(/^www\./, '')
    .replace(/\/.*$/, '')
    .toLowerCase()
    .trim();

  if (!cleanDomain || !cleanDomain.includes('.')) {
    return { success: false, error: 'Невірний формат домену' };
  }

  var webhookUrl = 'https://n8n.rnd.webpromo.tools/webhook/seo-organic-traffic-v74';

  var payload = {
    domain: cleanDomain,
    country: 'ua',
    top_pages_limit: 50
  };

  var options = {
    method: 'POST',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  try {
    var response = UrlFetchApp.fetch(webhookUrl, options);
    var result = JSON.parse(response.getContentText());

    return {
      success: true,
      spreadsheetUrl: result.spreadsheet_url,
      message: result.message || 'Аудит запущено!'
    };
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}

// ============================================
// БЕКЕНД: Семантичне ядро (GKP)
// ============================================

function submitGKP(formData) {
  // Валідація
  if (!formData.seed_keywords || formData.seed_keywords.length === 0) {
    return { success: false, error: 'Введіть хоча б одне ключове слово' };
  }

  var webhookUrl = 'https://n8n.rnd.webpromo.tools/webhook/gkp-report';

  // Парсинг url_mapping з текстового поля (формат: keyword | url)
  var urlMapping = {};
  if (formData.url_mapping_text) {
    var lines = formData.url_mapping_text.split('\n');
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (!line) continue;
      var parts = line.split('|');
      if (parts.length === 2) {
        urlMapping[parts[0].trim()] = parts[1].trim();
      }
    }
  }

  var payload = {
    doc_name: formData.doc_name || 'GKP Report - ' + new Date().toISOString().slice(0, 10),
    language: formData.language || '1000',
    geo_target: formData.geo_target || '2804',
    seed_keywords: formData.seed_keywords,
    url_mapping: urlMapping,
    limit: parseInt(formData.limit) || 600
  };

  var options = {
    method: 'POST',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  try {
    var response = UrlFetchApp.fetch(webhookUrl, options);
    var result = JSON.parse(response.getContentText());

    return {
      success: true,
      spreadsheetUrl: result.spreadsheet_url,
      totalKeywords: result.total_keywords,
      totalClusters: result.total_clusters,
      message: 'Знайдено ' + result.total_keywords + ' ключових слів у ' + result.total_clusters + ' кластерах'
    };
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}