// Проверка полноты данных за последние 15 месяцев
// v7: Увеличен горизонт сбора с 13 до 15 месяцев
// v6: Минимум 2 сайта в задаче (SimilarWeb требует сравнение)
const competitors = $('Читаем всех конкурентов').all();

let existingQueue = [];
try {
  existingQueue = $('Читаем очередь (проверка)').all();
} catch (e) {}

let existingSwData = [];
try {
  existingSwData = $('Читаем существующие данные').all();
} catch (e) {}

const MAX_SITES_PER_REQUEST = 5;
const MIN_SITES_PER_REQUEST = 2; // v6: SimilarWeb требует минимум 2 сайта для сравнения

function normalizeDomain(url) {
  if (!url) return '';
  return url.replace(/^https?:\/\/$/i, '').replace(/^www\./i, '').replace(/\/+$/, '').toLowerCase().trim();
}

function getLast15Months() {
  const months = [];
  const now = new Date();
  for (let i = 1; i <= 15; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    months.push(`${year}.${month}`);
  }
  return months;
}

const last15Months = getLast15Months();

const clientCompetitors = new Map();
competitors.forEach(row => {
  const client = normalizeDomain(row.json.client_site);
  const competitor = normalizeDomain(row.json.competitors_site);
  if (client && competitor) {
    if (!clientCompetitors.has(client)) clientCompetitors.set(client, []);
    if (!clientCompetitors.get(client).includes(competitor)) clientCompetitors.get(client).push(competitor);
  }
});

const existingQueueKeys = new Set();
existingQueue.forEach(row => {
  const key = `${row.json.client_site}_${row.json.period}_chunk${row.json.chunk_index}`;
  existingQueueKeys.add(key);
});

const existingDataKeys = new Set();
existingSwData.forEach(row => {
  const site = normalizeDomain(row.json.site);
  const period = row.json.period;
  if (site && period) existingDataKeys.add(`${site}_${period}`);
});

console.log(`Existing SW data entries: ${existingDataKeys.size}`);
console.log(`Existing queue entries: ${existingQueueKeys.size}`);

function chunkArray(array, chunkSize) {
  const chunks = [];
  for (let i = 0; i < array.length; i += chunkSize) chunks.push(array.slice(i, i + chunkSize));
  return chunks;
}

function allSitesHaveData(sites, period) {
  return sites.every(site => existingDataKeys.has(`${site}_${period}`));
}

const queueTasks = [];
let skippedByData = 0;
let skippedByQueue = 0;
let skippedNoCompetitors = 0;

clientCompetitors.forEach((competitorsList, clientSite) => {
  // v6: Пропускаем клиентов без конкурентов
  if (competitorsList.length === 0) {
    skippedNoCompetitors++;
    console.log(`Skipped ${clientSite}: no competitors`);
    return;
  }

  const competitorChunks = chunkArray(competitorsList, MAX_SITES_PER_REQUEST - 1);
  
  competitorChunks.forEach((chunk, chunkIndex) => {
    // v6: Пропускаем пустые chunks
    if (chunk.length === 0) {
      return;
    }
    
    last15Months.forEach((period, periodIndex) => {
      const sitesInRequest = [clientSite, ...chunk];
      
      // v6: Проверяем минимальное количество сайтов
      if (sitesInRequest.length < MIN_SITES_PER_REQUEST) {
        console.log(`Skipped ${clientSite} ${period}: only ${sitesInRequest.length} site(s)`);
        return;
      }
      
      const sitesList = sitesInRequest.join(',');

      if (allSitesHaveData(sitesInRequest, period)) {
        skippedByData++;
        return;
      }

      const dedupeKey = `${clientSite}_${period}_chunk${chunkIndex}`;
      if (existingQueueKeys.has(dedupeKey)) {
        skippedByQueue++;
        return;
      }

      const taskId = `${clientSite}_${period}_chunk${chunkIndex}`;
      queueTasks.push({
        queue_id: taskId,
        client_site: clientSite,
        sites_list: sitesList,
        chunk_index: chunkIndex,
        total_chunks: competitorChunks.length,
        period: period,
        status: 'pending',
        priority: periodIndex,
        created_at: new Date().toISOString().replace('T', ' ').substring(0, 19),
        task_id: '',
        error_message: ''
      });
    });
  });
});

queueTasks.sort((a, b) => b.priority - a.priority);

const summary = {
  totalClients: clientCompetitors.size,
  totalTasks: queueTasks.length,
  skippedByExistingData: skippedByData,
  skippedByExistingQueue: skippedByQueue,
  skippedNoCompetitors: skippedNoCompetitors,
  periods: last15Months,
  maxSitesPerRequest: MAX_SITES_PER_REQUEST,
  minSitesPerRequest: MIN_SITES_PER_REQUEST
};

console.log('Queue tasks summary:', JSON.stringify(summary));

if (queueTasks.length === 0) {
  return [{ json: { noNewTasks: true, summary } }];
}

return queueTasks.map(task => ({ json: task }));

