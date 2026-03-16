// ============================================
// РОУТИНГ
// ============================================

function doGet(e) {
  return HtmlService.createHtmlOutputFromFile('analiz_domenu_form')
    .setTitle('SEO Audit — Мастер')
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
// УТИЛІТИ: Папка менеджера на Google Drive
// ============================================

var ROOT_SEO_FOLDER_ID = '1A3Ak929G1c4XmZpPtI2FP4glrFE2-Bx2';

function findOrCreateManagerFolder(email) {
  var rootFolder = DriveApp.getFolderById(ROOT_SEO_FOLDER_ID);
  var folders = rootFolder.getFoldersByName(email);
  if (folders.hasNext()) {
    return folders.next().getId();
  }
  var newFolder = rootFolder.createFolder(email);
  return newFolder.getId();
}

function moveFileToFolder(fileId, targetFolderId) {
  var file = DriveApp.getFileById(fileId);
  var targetFolder = DriveApp.getFolderById(targetFolderId);
  targetFolder.addFile(file);
  var parents = file.getParents();
  while (parents.hasNext()) {
    var parent = parents.next();
    if (parent.getId() !== targetFolderId) {
      parent.removeFile(file);
    }
  }
}

function extractFileIdFromUrl(url) {
  var match = url.match(/\/d\/([a-zA-Z0-9_-]+)/);
  return match ? match[1] : null;
}

// ============================================
// БЕКЕНД: GKP Розширення семантики
// ============================================

function submitGKPIdeas(formData) {
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
    muteHttpExceptions: true,
    timeout: 600
  };

  try {
    var response = UrlFetchApp.fetch(webhookUrl, options);
    var result = JSON.parse(response.getContentText());
    return { success: true, spreadsheetUrl: result.spreadsheetUrl || result.url || '', message: 'Розширення семантики завершено' };
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}

// ============================================
// БЕКЕНД: GKP Метрики ключових слів
// ============================================

function submitGKPMetrics(formData) {
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
    muteHttpExceptions: true,
    timeout: 600
  };

  try {
    var response = UrlFetchApp.fetch(webhookUrl, options);
    var result = JSON.parse(response.getContentText());
    return { success: true, spreadsheetUrl: result.spreadsheetUrl || result.url || '', message: 'Метрики отримано' };
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}

// ============================================
// БЕКЕНД: AI Аналіз таблиці
// ============================================

function submitAIAnalysis(formData) {
  // Support 3 formats:
  // 1. String URL (legacy single competitor)
  // 2. { url: "...", manager_email: "..." } (legacy single)
  // 3. { urls: ["...", "..."], manager_email: "..." } (new multi-competitor)
  var urls = [];
  var managerEmail = '';

  if (typeof formData === 'string') {
    urls = [formData];
  } else if (formData.urls && formData.urls.length > 0) {
    urls = formData.urls;
    managerEmail = formData.manager_email || '';
  } else if (formData.url) {
    urls = [formData.url];
    managerEmail = formData.manager_email || '';
  }

  // Validate all URLs
  for (var i = 0; i < urls.length; i++) {
    if (!urls[i] || !urls[i].includes('docs.google.com/spreadsheets')) {
      return { success: false, error: 'Конкурент ' + (i + 1) + ': невірний формат посилання на таблицю' };
    }
  }

  if (urls.length === 0) {
    return { success: false, error: 'Додайте хоча б одне посилання на таблицю' };
  }

  var webhookUrl = 'https://n8n.rnd.webpromo.tools/webhook/seo-audit-ai-report';

  var payload = {
    urls: urls
  };

  if (managerEmail) {
    payload.manager_email = managerEmail;
  }

  var options = {
    method: 'POST',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  try {
    var response = UrlFetchApp.fetch(webhookUrl, options);
    var result = JSON.parse(response.getContentText());

    // n8n responds immediately with status "processing" and docUrl.
    // The document is being formatted in the background.
    return {
      success: true,
      status: result.status || 'processing',
      docUrl: result.docUrl,
      docId: result.docId || extractFileIdFromUrl(result.docUrl || ''),
      competitorsCount: result.competitorsCount || urls.length,
      message: 'Документ створено. Форматування у фоні...'
    };
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}

// ============================================
// БЕКЕНД: Перевірка готовності AI документа
// ============================================

function checkDocStatus(docId) {
  try {
    var url = 'https://www.googleapis.com/drive/v3/files/' + docId + '?fields=properties,name';
    var response = UrlFetchApp.fetch(url, {
      headers: { 'Authorization': 'Bearer ' + ScriptApp.getOAuthToken() },
      muteHttpExceptions: true
    });

    if (response.getResponseCode() !== 200) {
      return { success: false, error: 'Файл не знайдено (код ' + response.getResponseCode() + ')' };
    }

    var data = JSON.parse(response.getContentText());
    var isComplete = data.properties && data.properties.seo_audit_status === 'complete';

    return {
      success: true,
      isComplete: isComplete,
      docName: data.name || ''
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

  if (formData.manager_email) {
    payload.manager_email = formData.manager_email;
  }

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

    // Move spreadsheet to manager folder if email provided
    if (formData.manager_email && result.spreadsheetUrl) {
      try {
        var sheetId = extractFileIdFromUrl(result.spreadsheetUrl);
        if (sheetId) {
          var folderId = findOrCreateManagerFolder(formData.manager_email);
          moveFileToFolder(sheetId, folderId);
        }
      } catch (moveErr) {
        // Non-critical: sheet created but not moved
      }
    }

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
