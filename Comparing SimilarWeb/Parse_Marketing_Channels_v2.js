// Парсер Marketing Channels v2.0
// v2.0:
//   - переход на новые имена капчеров (Search - Organic/Paid, Social - Organic/Paid, Gen AI, Affiliates)
//   - убран алиас Sosial/Display Search (старый формат больше не приходит)
//   - в выход добавлены: Social Organic, Social Paid, Affiliates, Gen AI
//   - убран Social (расщеплён на organic/paid)
const input = $input.first().json;

const body = input.body || input;
const taskStatus = body?.task?.status || input.taskStatus;

if (taskStatus !== 'successful' && taskStatus !== 'completed') {
  return [{ json: { error: 'Task not successful', taskStatus, sheetsRows: [] } }];
}

const rawData = body?.task?.capturedTexts || {};
const taskId = body?.task?.id || input.taskId || 'unknown';
const originUrl = body?.task?.inputParameters?.originUrl || input.originUrl || '';

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

// Функция очистки markdown ссылок [domain.com](http://domain.com) -> domain.com
function cleanMarkdownLink(text) {
  if (!text) return text;
  const match = text.match(/^\[([^\]]+)\]/);
  return match ? match[1] : text;
}

function extractLegendData(html) {
  if (!html) return {};
  const sites = {};
  const patterns = [
    /data-automation-title="true"[^>]*>([^<]+)<\/label>[\s\S]*?data-automation-value="true"[^>]*>([^<]+)<\/label>/g,
    /class="[^"]*iUaIjL[^"]*">([^<]+)<\/label>[\s\S]{0,300}?class="[^"]*gzsEum[^"]*">([^<]+)<\/label>/g
  ];
  patterns.forEach(pattern => {
    let match;
    while ((match = pattern.exec(html)) !== null) {
      let site = match[1].trim();
      const value = match[2].trim();
      site = cleanMarkdownLink(site);
      if (site && value && site.includes('.') && /^[a-zA-Z0-9]/.test(site)) {
        if (!sites[site]) sites[site] = value;
      }
    }
  });
  return sites;
}

const direct        = extractLegendData(data['Direct']);
const organicSearch = extractLegendData(data['Search - Organic']);
const paidSearch    = extractLegendData(data['Search - Paid']);
const displayAds    = extractLegendData(data['Display Ads']);
const socialOrganic = extractLegendData(data['Social - Organic']);
const socialPaid    = extractLegendData(data['Social - Paid']);
const email         = extractLegendData(data['Email']);
const affiliates    = extractLegendData(data['Affiliates']);
const genAi         = extractLegendData(data['Gen AI']);

const today = new Date().toISOString().split('T')[0];

const allSites = new Set();
[direct, organicSearch, paidSearch, displayAds, socialOrganic, socialPaid, email, affiliates, genAi]
  .forEach(channel => Object.keys(channel).forEach(site => allSites.add(site)));

if (allSites.size === 0 && sitesFromUrl.length > 0) {
  sitesFromUrl.forEach(site => allSites.add(site));
}

const sitesArray = Array.from(allSites);

const sheetsRows = sitesArray.map((site) => ({
  'date': today,
  'period': periodFormatted,
  'client_site': clientSite,
  'site': site,
  'type': site === clientSite ? 'client' : 'competitor',
  'Direct':         direct[site]        || '',
  'Organic Search': organicSearch[site] || '',
  'Paid Search':    paidSearch[site]    || '',
  'Display Ads':    displayAds[site]    || '',
  'Social Organic': socialOrganic[site] || '',
  'Social Paid':    socialPaid[site]    || '',
  'Email':          email[site]         || '',
  'Affiliates':     affiliates[site]    || '',
  'Gen AI':         genAi[site]         || '',
  'Task ID': taskId,
  'Queue ID': queueId,
  'key': `${periodFormatted}_${site}`
}));

return [{
  json: {
    taskId,
    queueId,
    type: 'marketing_channels',
    periodFormatted,
    clientSite,
    channels: { direct, organicSearch, paidSearch, displayAds, socialOrganic, socialPaid, email, affiliates, genAi },
    sheetsRows,
    sitesCount: sitesArray.length,
    raw: data
  }
}];
