function doGet() {
  return HtmlService.createHtmlOutputFromFile('form')
    .setTitle('SEO Аудит 2.0')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function submitAudit(domain) {
  // Валідація домену
  const cleanDomain = domain
    .replace(/^https?:\/\//, '')
    .replace(/^www\./, '')
    .replace(/\/.*$/, '')
    .toLowerCase()
    .trim();
  
  if (!cleanDomain || !cleanDomain.includes('.')) {
    return { success: false, error: 'Невірний формат домену' };
  }
  
  // Відправка запиту до n8n
  const webhookUrl = 'https://n8n.rnd.webpromo.tools/webhook/seo-organic-traffic-v74';
  
  const payload = {
    domain: cleanDomain,
    country: 'ua',
    top_pages_limit: 50
  };
  
  const options = {
    method: 'POST',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  try {
    const response = UrlFetchApp.fetch(webhookUrl, options);
    const result = JSON.parse(response.getContentText());
    
    return {
      success: true,
      spreadsheetUrl: result.spreadsheet_url,
      message: result.message || 'Аудит запущено!'
    };
  } catch (error) {
    return { success: false, error: error.toString() };
  }
}