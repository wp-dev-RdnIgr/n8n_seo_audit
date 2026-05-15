// Парсер Performance данных v4.2
// v4.2: В sheetsRows добавлены Visits Per Visitor, Deduplicated Audience, Page Views
//       (раньше парсер их извлекал, но не пробрасывал в upsert → в БД оставалось '').
// v4.1: Добавлена поддержка markdown ссылок из Browse.ai
// v4: Только Engagement данные (каналы перенесены в Marketing Channels Robot)
const input = $input.first().json;

const body = input.body || input;
const rawData = body?.task?.capturedTexts || {};
const taskId = body?.task?.id || input.taskId || 'unknown';
const originUrl = body?.task?.inputParameters?.originUrl || input.originUrl || '';
const inputSites = input.sites || [];

const keyMatch = originUrl.match(/key=([^&]+)/);
let sitesFromUrl = [];
if (keyMatch) {
  sitesFromUrl = decodeURIComponent(keyMatch[1]).split(',');
}
const clientSite = sitesFromUrl[0] || '';

const qidMatch = originUrl.match(/qid=([^&]+)/);
const queueId = qidMatch ? qidMatch[1] : '';

let periodFormatted = '';
const periodUrlMatch = originUrl.match(/\/804\/(\d{4}\.\d{1,2})-\d{4}\.\d{1,2}/);
if (periodUrlMatch) {
  const [y, m] = periodUrlMatch[1].split('.');
  periodFormatted = y + '.' + m.padStart(2, '0');
}
if (!periodFormatted && queueId) {
  const queuePeriodMatch = queueId.match(/_(\d{4}\.\d{1,2})_/);
  if (queuePeriodMatch) {
    const [y, m] = queuePeriodMatch[1].split('.');
    periodFormatted = y + '.' + m.padStart(2, '0');
  }
}
if (!periodFormatted) {
  const now = new Date();
  periodFormatted = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, '0')}`;
}

let data = {};
if (Array.isArray(rawData)) {
  rawData.forEach(item => {
    const key = item.name || item.key;
    const value = item.newText || item.text || item.value;
    if (key && value) data[key] = value;
  });
} else {
  data = rawData;
}

function isLoading(html) {
  if (!html) return true;
  return html.includes('LoadingContainer') || html.includes('linearGradient id="lineGray"');
}

function extractEngagementData(html) {
  if (!html || isLoading(html)) return null;
  const result = {};
  
  // Паттерн с поддержкой markdown ссылок [domain.com](http://domain.com)
  const domainPattern = /DomainWrapper[^>]*>\s*\[?([a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,})\]?(?:\([^)]*\))?\s*<\/span>/g;
  const domains = [];
  let match;
  while ((match = domainPattern.exec(html)) !== null) {
    domains.push(match[1].trim());
  }
  
  if (domains.length === 0) return null;
  
  domains.forEach(domain => {
    // Паттерн для ячеек с поддержкой markdown в data-automation
    const escapedDomain = domain.replace(/\./g, '\\.');
    const cellPattern = new RegExp(
      'data-automation="MiniFlexTable-cell [^"]*' + escapedDomain + '[^"]*"[\\s\\S]*?<span[^>]*class="[^"]*value[^"]*"[^>]*>([\\s\\S]*?)</span>',
      'g'
    );
    
    const values = [];
    let cellMatch;
    while ((cellMatch = cellPattern.exec(html)) !== null) {
      let val = cellMatch[1]
        .replace(/<svg[\s\S]*?<\/svg>/g, '')
        .replace(/<div[\s\S]*?<\/div>/g, '')
        .replace(/<[^>]+>/g, '')
        .trim();
      if (val) values.push(val);
    }
    
    if (values.length >= 5) {
      result[domain] = {
        monthlyVisits: values[0] || '',
        uniqueVisitors: values[1] || '',
        visitsPerVisitor: values[2] || '',
        deduplicatedAudience: values[3] || '',
        visitDuration: values[4] || '',
        pagesPerVisit: values[5] || '',
        bounceRate: values[6] || '',
        pageViews: values[7] || ''
      };
    }
  });
  
  return Object.keys(result).length > 0 ? result : null;
}

let engagement = null;
if (!isLoading(data['Engagement'])) {
  engagement = extractEngagementData(data['Engagement']);
}
if (!engagement && data['Engagement 2']) {
  engagement = extractEngagementData(data['Engagement 2']);
}

const today = new Date().toISOString().split('T')[0];

const allSites = new Set();
if (engagement) {
  Object.keys(engagement).forEach(site => allSites.add(site));
}
if (allSites.size === 0 && sitesFromUrl.length > 0) {
  sitesFromUrl.forEach(site => allSites.add(site));
}
if (allSites.size === 0 && inputSites.length > 0) {
  inputSites.forEach(site => allSites.add(site));
}

const sitesArray = Array.from(allSites);

const sheetsRows = sitesArray.map((site) => {
  const eng = engagement?.[site] || {};
  return {
    'date': today,
    'period': periodFormatted,
    'client_site': clientSite,
    'site': site,
    'type': site === clientSite ? 'client' : 'competitor',
    'Monthly Visits': eng.monthlyVisits || '',
    'Unique Visitors': eng.uniqueVisitors || '',
    'Visits Per Visitor': eng.visitsPerVisitor || '',
    'Deduplicated Audience': eng.deduplicatedAudience || '',
    'Visit Duration': eng.visitDuration || '',
    'Pages/Visit': eng.pagesPerVisit || '',
    'Bounce Rate': eng.bounceRate || '',
    'Page Views': eng.pageViews || '',
    'Task ID': taskId,
    'Queue ID': queueId,
    'key': `${periodFormatted}_${site}`
  };
});

return [{
  json: {
    taskId,
    queueId,
    type: 'performance',
    periodFormatted,
    clientSite,
    engagement,
    sheetsRows,
    sitesCount: sitesArray.length,
    raw: data
  }
}];

