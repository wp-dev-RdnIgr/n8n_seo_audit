const fs = require('fs');

const INPUT = '/home/user/n8n_seo_audit/Comparing SimilarWeb/Comparing SimilarWeb (1).json';
const workflow = JSON.parse(fs.readFileSync(INPUT, 'utf8'));

// ========================
// 1. NODES TO REMOVE
// ========================
const nodesToRemove = new Set([
  // Google Drive pipeline
  "Извлекаем уникальных клиентов",
  "Подготовка запроса Drive",
  "Поиск папки клиента",
  "Анализ результата поиска",
  "Папка существует?",
  "Создаём папку клиента",
  "Создаём таблицу клиента",
  "Создаём лист Данные",
  "Записываем заголовки",
  "Сохраняем клиента",
  "Telegram: Новый клиент",
  // Performance upsert chain
  "Читаем Клиенты",
  "Маршрутизация по клиентам",
  "Есть данные клиента?",
  "Читаем таблицу для upsert",
  "Upsert логика Performance",
  "Update или Append?",
  "Update строку",
  "Append строку",
  // MC upsert chain
  "Читаем Клиенты для MC",
  "Маршрутизация MC по клиентам",
  "Есть MC данные клиента?",
  "Читаем таблицу для MC upsert",
  "Upsert логика MC",
  "MC Update или Append?",
  "MC Update строку",
  "MC Append строку",
  // AI Traffic upsert chain
  "Читаем Клиенты для AI",
  "Маршрутизация AI по клиентам",
  "Есть AI данные клиента?",
  "Читаем таблицу для AI upsert",
  "Upsert логика AI Traffic",
  "AI Update или Append?",
  "AI Update строку",
  "AI Append строку",
]);

// Remove nodes
workflow.nodes = workflow.nodes.filter(n => !nodesToRemove.has(n.name));

// ========================
// 2. POSTGRES CREDENTIAL
// ========================
const pgCred = {
  postgres: {
    id: "supabasePgCred",
    name: "Supabase - Postgres account"
  }
};

function makePgNode(overrides) {
  return {
    parameters: {
      operation: "executeQuery",
      query: overrides.query,
      options: {}
    },
    id: overrides.id,
    name: overrides.name,
    type: "n8n-nodes-base.postgres",
    typeVersion: 2.5,
    position: overrides.position,
    credentials: pgCred,
    ...(overrides.notes ? { notes: overrides.notes } : {})
  };
}

// ========================
// 3. REPLACE Google Sheets nodes with Postgres
// ========================
const replacements = {
  "Читаем всех конкурентов": {
    query: "SELECT c.client_site, comp.competitor_site as competitors_site FROM competitors comp JOIN clients c ON c.id = comp.client_id"
  },
  "Читаем очередь (проверка)": {
    query: "SELECT queue_id, client_site, sites_list, chunk_index, total_chunks, period, status, priority, task_id, error_message, created_at FROM task_queue"
  },
  "Читаем очередь": {
    query: "SELECT queue_id, client_site, sites_list, chunk_index, total_chunks, period, status, priority, task_id, error_message, created_at FROM task_queue"
  },
  "Добавляем в очередь": {
    query: "=INSERT INTO task_queue (queue_id, client_id, client_site, sites_list, chunk_index, total_chunks, period, status, priority, task_id, error_message)\nSELECT\n  '{{ $json.queue_id }}',\n  c.id,\n  '{{ $json.client_site }}',\n  '{{ $json.sites_list }}',\n  {{ $json.chunk_index }},\n  {{ $json.total_chunks }},\n  '{{ $json.period }}',\n  '{{ $json.status }}',\n  {{ $json.priority }},\n  '{{ $json.task_id }}',\n  '{{ $json.error_message }}'\nFROM clients c WHERE c.client_site = '{{ $json.client_site }}'\nON CONFLICT (queue_id) DO NOTHING"
  },
  "Статус: processing": {
    query: "=UPDATE task_queue SET status = 'processing' WHERE queue_id = '{{ $json.queue_id }}'"
  },
  "Обновляем статус очереди: done": {
    query: "=UPDATE task_queue SET status = 'done', task_id = '{{ $json.task_id }}' WHERE queue_id = '{{ $json.queue_id }}'"
  },
  "Логируем ошибку": {
    query: "=INSERT INTO error_logs (task_id, robot_type, period, sites, status, error_message, url)\nVALUES (\n  '{{ $json.task_id }}',\n  '{{ $json.robot_type }}',\n  '{{ $json.period }}',\n  '{{ $json.sites }}',\n  '{{ $json.status }}',\n  '{{ $json.error_message }}',\n  '{{ $json.url }}'\n)"
  }
};

workflow.nodes = workflow.nodes.map(node => {
  if (replacements[node.name]) {
    return makePgNode({
      id: node.id,
      name: node.name,
      position: node.position,
      query: replacements[node.name].query,
      notes: node.notes
    });
  }
  return node;
});

// ========================
// 4. ADD NEW UPSERT NODES
// ========================
workflow.nodes.push(makePgNode({
  id: "perf-upsert-sb-001",
  name: "Upsert Performance в Supabase",
  position: [-752, 400],
  query: "=SELECT upsert_similarweb_data(\n  p_client_site := '{{ $json.client_site }}',\n  p_site := '{{ $json.site }}',\n  p_site_type := '{{ $json.type }}',\n  p_period := '{{ $json.period }}',\n  p_monthly_visits := '{{ $json[\"Monthly Visits\"] }}',\n  p_unique_visitors := '{{ $json[\"Unique Visitors\"] }}',\n  p_visit_duration := '{{ $json[\"Visit Duration\"] }}',\n  p_pages_per_visit := '{{ $json[\"Pages/Visit\"] }}',\n  p_bounce_rate := '{{ $json[\"Bounce Rate\"] }}',\n  p_visits_per_visitor := '{{ $json[\"Visits Per Visitor\"] }}',\n  p_deduplicated_audience := '{{ $json[\"Deduplicated Audience\"] }}',\n  p_page_views := '{{ $json[\"Page Views\"] }}',\n  p_task_id := '{{ $json[\"Task ID\"] }}',\n  p_queue_id := '{{ $json[\"Queue ID\"] }}'\n);",
  notes: "Merge-upsert Performance данных в Supabase через RPC"
}));

workflow.nodes.push(makePgNode({
  id: "mc-upsert-sb-001",
  name: "Upsert MC в Supabase",
  position: [-1408, 800],
  query: "=SELECT upsert_similarweb_data(\n  p_client_site := '{{ $json.client_site }}',\n  p_site := '{{ $json.site }}',\n  p_site_type := '{{ $json.type }}',\n  p_period := '{{ $json.period }}',\n  p_direct := '{{ $json.Direct }}',\n  p_organic_search := '{{ $json[\"Organic Search\"] }}',\n  p_paid_search := '{{ $json[\"Paid Search\"] }}',\n  p_display_ads := '{{ $json[\"Display Ads\"] }}',\n  p_social := '{{ $json.Social }}',\n  p_email := '{{ $json.Email }}',\n  p_task_id := '{{ $json[\"Task ID\"] }}',\n  p_queue_id := '{{ $json[\"Queue ID\"] }}'\n);",
  notes: "Merge-upsert Marketing Channels данных в Supabase через RPC"
}));

workflow.nodes.push(makePgNode({
  id: "ai-upsert-sb-001",
  name: "Upsert AI в Supabase",
  position: [-1184, 400],
  query: "=SELECT upsert_similarweb_data(\n  p_client_site := '{{ $json.client_site }}',\n  p_site := '{{ $json.site }}',\n  p_site_type := '{{ $json.type }}',\n  p_period := '{{ $json.period }}',\n  p_ai_traffic := '{{ $json[\"AI Traffic\"] }}',\n  p_task_id := '{{ $json[\"Task ID\"] }}',\n  p_queue_id := '{{ $json[\"Queue ID\"] }}'\n);",
  notes: "Merge-upsert AI Traffic данных в Supabase через RPC"
}));

// ========================
// 5. MODIFY Parse Performance Data - add 3 new metrics to sheetsRows
// ========================
const perfNode = workflow.nodes.find(n => n.name === "Parse Performance Data");
if (perfNode) {
  perfNode.parameters.jsCode = perfNode.parameters.jsCode.replace(
    "'Bounce Rate': eng.bounceRate || '',\n    'Direct': '',",
    "'Bounce Rate': eng.bounceRate || '',\n    'Visits Per Visitor': eng.visitsPerVisitor || '',\n    'Deduplicated Audience': eng.deduplicatedAudience || '',\n    'Page Views': eng.pageViews || '',\n    'Direct': '',"
  );
}

// ========================
// 6. MODIFY Format Performance Report - add 3 new metrics
// ========================
const fmtPerfNode = workflow.nodes.find(n => n.name === "Format Performance Report");
if (fmtPerfNode) {
  fmtPerfNode.parameters.jsCode = fmtPerfNode.parameters.jsCode.replace(
    "if (metrics.bounceRate) report += `   📉 Bounce Rate: ${metrics.bounceRate}\\n`;",
    "if (metrics.bounceRate) report += `   📉 Bounce Rate: ${metrics.bounceRate}\\n`;\n    if (metrics.visitsPerVisitor) report += `   👤 Visits/Visitor: ${metrics.visitsPerVisitor}\\n`;\n    if (metrics.deduplicatedAudience) report += `   🎯 Deduplicated: ${metrics.deduplicatedAudience}\\n`;\n    if (metrics.pageViews) report += `   📝 Page Views: ${metrics.pageViews}\\n`;"
  );
}

// ========================
// 7. REWRITE CONNECTIONS
// ========================
workflow.connections = {
  "Cron: Проверка полноты (2x в день)": {
    main: [[
      { node: "Читаем всех конкурентов", type: "main", index: 0 },
      { node: "Читаем очередь (проверка)", type: "main", index: 0 }
    ]]
  },
  "Читаем всех конкурентов": {
    main: [[
      { node: "Объединяем данные", type: "main", index: 0 }
    ]]
  },
  "Читаем очередь (проверка)": {
    main: [[
      { node: "Объединяем данные", type: "main", index: 1 }
    ]]
  },
  "Объединяем данные": {
    main: [[
      { node: "Анализ полноты данных", type: "main", index: 0 }
    ]]
  },
  "Анализ полноты данных": {
    main: [[
      { node: "Есть новые задачи?", type: "main", index: 0 }
    ]]
  },
  "Есть новые задачи?": {
    main: [[
      { node: "Добавляем в очередь", type: "main", index: 0 }
    ]]
  },
  "Добавляем в очередь": {
    main: [[
      { node: "Telegram: Задачи добавлены", type: "main", index: 0 }
    ]]
  },
  "Cron: Обработка очереди": {
    main: [[
      { node: "Читаем очередь", type: "main", index: 0 }
    ]]
  },
  "Читаем очередь": {
    main: [[
      { node: "Filter: Только pending", type: "main", index: 0 }
    ]]
  },
  "Filter: Только pending": {
    main: [[
      { node: "Подготовка задач (макс 9)", type: "main", index: 0 }
    ]]
  },
  "Подготовка задач (макс 9)": {
    main: [[
      { node: "Рандомная пауза", type: "main", index: 0 }
    ]]
  },
  "Рандомная пауза": {
    main: [[
      { node: "Подготовка URL", type: "main", index: 0 }
    ]]
  },
  "Подготовка URL": {
    main: [[
      { node: "Статус: processing", type: "main", index: 0 }
    ]]
  },
  "Статус: processing": {
    main: [[
      { node: "Запуск Performance Robot", type: "main", index: 0 }
    ]]
  },
  "Запуск Performance Robot": {
    main: [[
      { node: "Ждём Performance", type: "main", index: 0 }
    ]]
  },
  "Ждём Performance": {
    main: [[
      { node: "Запуск Marketing Channels Robot", type: "main", index: 0 }
    ]]
  },
  "Запуск Marketing Channels Robot": {
    main: [[
      { node: "Ждём Marketing Channels", type: "main", index: 0 }
    ]]
  },
  "Ждём Marketing Channels": {
    main: [[
      { node: "Запуск AI Traffic Robot", type: "main", index: 0 }
    ]]
  },
  "Webhook: Performance Results": {
    main: [[
      { node: "Проверка статуса задачи", type: "main", index: 0 }
    ]]
  },
  "Проверка статуса задачи": {
    main: [[
      { node: "Ошибка или успех?", type: "main", index: 0 }
    ]]
  },
  "Ошибка или успех?": {
    main: [
      [{ node: "Логируем ошибку", type: "main", index: 0 }],
      [{ node: "Parse Performance Data", type: "main", index: 0 }]
    ]
  },
  "Логируем ошибку": {
    main: [[
      { node: "Telegram: Ошибка", type: "main", index: 0 }
    ]]
  },
  "Parse Performance Data": {
    main: [[
      { node: "Split Out: Performance", type: "main", index: 0 },
      { node: "Format Performance Report", type: "main", index: 0 }
    ]]
  },
  "Split Out: Performance": {
    main: [[
      { node: "Подготовка обновления очереди", type: "main", index: 0 },
      { node: "Upsert Performance в Supabase", type: "main", index: 0 }
    ]]
  },
  "Подготовка обновления очереди": {
    main: [[
      { node: "Обновляем статус очереди: done", type: "main", index: 0 }
    ]]
  },
  "Format Performance Report": {
    main: [[
      { node: "Telegram: Performance", type: "main", index: 0 }
    ]]
  },
  "Webhook: Marketing Channels Results": {
    main: [[
      { node: "Parse Marketing Channels Data", type: "main", index: 0 }
    ]]
  },
  "Parse Marketing Channels Data": {
    main: [[
      { node: "Split Out: Marketing Channels", type: "main", index: 0 },
      { node: "Format MC Report", type: "main", index: 0 }
    ]]
  },
  "Split Out: Marketing Channels": {
    main: [[
      { node: "Upsert MC в Supabase", type: "main", index: 0 }
    ]]
  },
  "Format MC Report": {
    main: [[
      { node: "Telegram: Marketing Channels", type: "main", index: 0 }
    ]]
  },
  "Webhook: AI Traffic Results": {
    main: [[
      { node: "Parse AI Traffic Data", type: "main", index: 0 }
    ]]
  },
  "Parse AI Traffic Data": {
    main: [[
      { node: "Split Out: AI Traffic", type: "main", index: 0 },
      { node: "Format AI Traffic Report", type: "main", index: 0 }
    ]]
  },
  "Split Out: AI Traffic": {
    main: [[
      { node: "Upsert AI в Supabase", type: "main", index: 0 }
    ]]
  },
  "Format AI Traffic Report": {
    main: [[
      { node: "Telegram: AI Traffic", type: "main", index: 0 }
    ]]
  }
};

// ========================
// VALIDATE & WRITE
// ========================
const output = JSON.stringify(workflow, null, 2);
// Verify valid JSON
JSON.parse(output);

// Verify node count
const nodeNames = workflow.nodes.map(n => n.name);
console.log(`Total nodes: ${nodeNames.length}`);
console.log('Nodes:', nodeNames.join(', '));

// Verify all connection targets exist
const nodeNameSet = new Set(nodeNames);
for (const [src, conn] of Object.entries(workflow.connections)) {
  if (!nodeNameSet.has(src)) {
    console.error(`CONNECTION ERROR: source "${src}" not found in nodes!`);
  }
  for (const outputs of conn.main) {
    for (const link of outputs) {
      if (!nodeNameSet.has(link.node)) {
        console.error(`CONNECTION ERROR: target "${link.node}" (from "${src}") not found in nodes!`);
      }
    }
  }
}

fs.writeFileSync(INPUT, output, 'utf8');
console.log('Workflow written successfully!');
