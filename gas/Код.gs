// ============================================
// РОУТИНГ: ?page=audit | ?page=master | ?page=gkp | ?page=gkp_ideas | ?page=gkp_metrics | ?page=pagespeed | ?page=pdf_audit | ?page=wizard
// ============================================

function doGet(e) {
  var page = (e && e.parameter && e.parameter.page) ? e.parameter.page : 'audit';

  var pages = {
    'audit':       { file: 'form', title: 'Аналіз домену' },
    'master':      { file: 'analiz_domenu_form', title: 'Аналіз домену — Мастер' },
    'gkp':         { file: 'gkp_form', title: 'Семантичне ядро (GKP)' },
    'gkp_ideas':   { file: 'gkp_ideas', title: 'GKP: Генерація ідей' },
    'gkp_metrics': { file: 'gkp_metrics', title: 'GKP: Метрики' },
    'pagespeed':   { file: 'pagespeed_form', title: 'PageSpeed Test' },
    'pdf_audit':   { file: 'pdf_audit_form', title: 'PDF Audit Parser' },
    'wizard':      { file: 'wizard_form', title: 'SEO Audit — Wizard' }
  };

  var config = pages[page] || pages['audit'];

  return HtmlService.createHtmlOutputFromFile(config.file)
    .setTitle(config.title)
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

// ============================================
// БЕКЕНД: Мастер — Аналіз домену (оркестратор)
// ============================================

function submitAnalizDomenu(formData) {
  // Валідація
  if (!formData.manager_email || !formData.manager_email.includes('@')) {
    return { success: false, error: 'Невірний email менеджера' };
  }

  var webhookUrl = 'https://n8n.rnd.webpromo.tools/webhook/analiz-domenu';

  var payload = {
    manager_email: formData.manager_email.trim()
  };

  // Опціональні блоки
  if (formData.client_domain) {
    payload.client_domain = formData.client_domain
      .replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/.*$/, '').toLowerCase().trim();
  }

  if (formData.competitors && formData.competitors.length > 0) {
    payload.competitors = formData.competitors;
  }

  if (formData.semantic_expansion && formData.semantic_expansion.spreadsheet_url) {
    payload.semantic_expansion = formData.semantic_expansion;
  }

  if (formData.metrics_collection && formData.metrics_collection.spreadsheet_url) {
    payload.metrics_collection = formData.metrics_collection;
  }

  if (formData.pagespeed && formData.pagespeed.spreadsheet_url) {
    payload.pagespeed = formData.pagespeed;
  }

  var options = {
    method: 'POST',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
    timeout: 600  // 10 хвилин — GKP/PageSpeed можуть бути довгими
  };

  try {
    var response = UrlFetchApp.fetch(webhookUrl, options);
    var result = JSON.parse(response.getContentText());

    if (result.status === 'completed') {
      return {
        success: true,
        folderUrl: result.folder_url || '',
        details: result.results || {},
        message: 'Аналіз завершено'
      };
    } else {
      return { success: false, error: result.error || 'Невідома помилка від воркфлоу' };
    }
  } catch (error) {
    return { success: false, error: error.toString() };
  }
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
// БЕКЕНД: AI Аналіз таблиці
// ============================================

function submitAIAnalysis(spreadsheetUrl) {
  if (!spreadsheetUrl || !spreadsheetUrl.includes('docs.google.com/spreadsheets')) {
    return { success: false, error: 'Невірний формат посилання на таблицю' };
  }

  var webhookUrl = 'https://n8n.rnd.webpromo.tools/webhook/seo-audit-ai-report';

  var payload = {
    url: spreadsheetUrl
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
      docUrl: result.docUrl,
      domain: result.domain,
      message: 'AI звіт створено для ' + result.domain
    };
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}

// ============================================
// БЕКЕНД: GKP Етап 1 - Генерація ідей
// ============================================

function submitGKPIdeas(formData) {
  // Валідація
  if (!formData.source_spreadsheet_id) {
    return { success: false, error: 'Вставте посилання на таблицю з seed-фразами' };
  }

  var webhookUrl = 'https://n8n.rnd.webpromo.tools/webhook/gkp-ideas';

  var payload = {
    doc_name: formData.doc_name || 'GKP Ideas - ' + new Date().toISOString().slice(0, 10),
    language: formData.language || '1036',
    geo_target: formData.geo_target || '2804',
    source_spreadsheet_id: formData.source_spreadsheet_id
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
      totalKeywords: result.total_keywords || 0,
      totalBatches: result.total_batches_processed || 0,
      message: 'Згенеровано ' + (result.total_keywords || 0) + ' ідей ключових слів'
    };
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}

// ============================================
// БЕКЕНД: GKP Етап 2 - Отримання метрик
// ============================================

function submitGKPMetrics(formData) {
  // Валідація
  if (!formData.source_spreadsheet_id) {
    return { success: false, error: 'Вставте посилання на таблицю з ключовими словами' };
  }

  var webhookUrl = 'https://n8n.rnd.webpromo.tools/webhook/gkp-metrics';

  var payload = {
    doc_name: formData.doc_name || 'GKP Metrics - ' + new Date().toISOString().slice(0, 10),
    language: formData.language || '1036',
    geo_target: formData.geo_target || '2804',
    source_spreadsheet_id: formData.source_spreadsheet_id
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
      totalKeywords: result.total_keywords || 0,
      keywordsWithData: result.keywords_with_data || 0,
      keywordsNoData: result.keywords_no_data || 0,
      message: 'Отримано метрики для ' + (result.total_keywords || 0) + ' ключових слів'
    };
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}

// ============================================
// БЕКЕНД: Семантичне ядро (GKP) - стара версія
// ============================================

function submitGKP(formData) {
  // Валідація
  if (!formData.seed_keywords || formData.seed_keywords.length === 0) {
    return { success: false, error: 'Введіть хоча б одне ключове слово' };
  }

  var webhookUrl = 'https://n8n.rnd.webpromo.tools/webhook/gkp-ideas';

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
    language: formData.language || '1036',
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

    var totalKeywords = result.total_keywords || 0;
    var totalSeeds = formData.seed_keywords.length;

    return {
      success: true,
      spreadsheetUrl: result.spreadsheet_url,
      totalKeywords: totalKeywords,
      totalClusters: totalSeeds,
      message: 'Знайдено ' + totalKeywords + ' ключових слів з ' + totalSeeds + ' сід-фраз'
    };
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}

// ============================================
// БЕКЕНД: PageSpeed Test
// ============================================

function submitPageSpeedTest(formData) {
  // Валідація
  if (!formData.spreadsheetUrl || !formData.spreadsheetUrl.includes('docs.google.com/spreadsheets')) {
    return { success: false, error: 'Невірний формат посилання на таблицю' };
  }

  // Витягти spreadsheetId з URL
  var match = formData.spreadsheetUrl.match(/\/d\/([a-zA-Z0-9_-]+)/);
  if (!match) {
    return { success: false, error: 'Не вдалося отримати ID таблиці' };
  }

  var webhookUrl = 'https://n8n.rnd.webpromo.tools/webhook/pagespeed-test';

  var payload = {
    spreadsheetId: match[1],
    testMobile: formData.testMobile !== false,
    testDesktop: formData.testDesktop !== false,
    batchSize: 5,
    delaySeconds: 5
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
      totalUrls: result.total_urls || 0,
      processingTime: result.processing_time_seconds || 0,
      message: 'PageSpeed тест завершено для ' + (result.total_urls || 0) + ' URL'
    };
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}

// ============================================
// БЕКЕНД: PDF Audit Parser
// ============================================

function submitPdfAuditParse(formData) {
  // Валідація
  if (!formData.pdfUrl || !formData.pdfUrl.includes('drive.google.com')) {
    return { success: false, error: 'Невірний формат посилання на PDF файл. Має бути Google Drive URL' };
  }

  var webhookUrl = 'https://n8n.rnd.webpromo.tools/webhook/parse-pdf-audit';

  var payload = {
    pdfUrl: formData.pdfUrl
  };

  var options = {
    method: 'POST',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
    timeout: 300000  // 5 хвилин таймаут для великих PDF
  };

  try {
    var response = UrlFetchApp.fetch(webhookUrl, options);
    var result = JSON.parse(response.getContentText());

    return {
      success: true,
      spreadsheetUrl: result.spreadsheetUrl,
      totalSheets: result.totalSheets || 15,
      processingTime: result.processingTime || 0,
      message: 'PDF документ успішно спарсено'
    };
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}
