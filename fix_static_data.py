#!/usr/bin/env python3
"""Fix the static data bug: replace $getWorkflowStaticData with $('Node').all() pattern."""

import json
import subprocess
import sys

N8N_URL = "https://n8n.rnd.webpromo.tools"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Zjc3NjZjMS04ZTZkLTQ3OGYtYTY2Ny05MzYxOWJhMzVkYmUiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzcxODY0MDI1fQ.pDWUjuqs6RF51PEKQtTHOUFJPvOF4YLFFsBWaCoL5I8"
WORKFLOW_ID = "BAekxapYobfgHYTt"

# ─── Step 1: Get the current live workflow ───
print("Step 1: Fetching current workflow from n8n...")
result = subprocess.run(
    ["curl", "-s", "-X", "GET",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}",
     "-H", f"X-N8N-API-KEY: {API_KEY}"],
    capture_output=True, text=True
)
wf = json.loads(result.stdout)
print(f"  Got workflow: {wf['name']} ({len(wf['nodes'])} nodes)")

# ─── Step 2: Fix the 3 nodes ───
print("\nStep 2: Fixing nodes...")

# New code for each node
NEW_PARSE_INPUT = r"""// Support old format (single url) and new format (urls array)
const body = $json.body || $json;

let urls = [];
if (body.urls && Array.isArray(body.urls)) {
  urls = body.urls;
} else if (body.url) {
  urls = [body.url];
} else if (body.spreadsheetId) {
  urls = ['spreadsheet://' + body.spreadsheetId];
}

const managerEmail = body.manager_email || '';

const items = urls.map((url, index) => {
  let spreadsheetId = '';
  if (url.startsWith('spreadsheet://')) {
    spreadsheetId = url.replace('spreadsheet://', '');
  } else {
    const match = url.match(/\/d\/([a-zA-Z0-9_-]+)/);
    spreadsheetId = match ? match[1] : url;
  }
  return {
    json: {
      spreadsheetId,
      url,
      manager_email: managerEmail,
      competitorIndex: index,
      totalCompetitors: urls.length
    }
  };
});

return items;"""

NEW_STORE_COMPETITOR_RESULT = r"""// Output competitor data directly — no static data needed.
// Prepare Document will read all iterations via $('Store Competitor Result').all()

const domain = $('Extract Domain & Folder').first().json.domain;
const dateToday = $('Extract Domain & Folder').first().json.dateToday;
const folderId = $('Extract Domain & Folder').first().json.folderId;
const managerEmail = $('Extract Domain & Folder').first().json.managerEmail || '';
const sections = $('Collect Sections').first().json;
const finalSummary = $json.message?.content || $json.content || $json.text || '';

return [{
  json: {
    domain,
    dateToday,
    folderId,
    managerEmail,
    finalSummary,
    sections: {
      section1: sections.section1 || '',
      section2: sections.section2 || '',
      section3: sections.section3 || '',
      section4: sections.section4 || '',
      section5: sections.section5 || '',
      section6: sections.section6 || ''
    }
  }
}];"""

NEW_PREPARE_DOCUMENT = r"""// Read ALL competitor results from the loop iterations
// $('Store Competitor Result').all() returns results from ALL SplitInBatches iterations
const allResults = $('Store Competitor Result').all();
const competitors = allResults.map(item => item.json);

if (competitors.length === 0) {
  throw new Error('No competitor data found. Store Competitor Result returned 0 items.');
}

const dateToday = competitors[0].dateToday;
const folderId = competitors[0].folderId;
const managerEmail = competitors[0].managerEmail || '';
const domains = competitors.map(c => c.domain);
const isMulti = competitors.length > 1;

// ── HELPERS ──

function cleanMarkdown(text) {
  return text
    .replace(/^#{1,4}\s*/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/^---+$/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

let tableCounter = 0;
const allTables = [];

function extractTables(text) {
  const tableRegex = /<<<\s*TABLE\s*>>>\s*([\s\S]*?)\s*<<<\s*TABLE_?END\s*>>[>\s})\].]*?/gi;
  const result = text.replace(tableRegex, (match, jsonStr) => {
    try {
      let cleaned = jsonStr.trim();
      cleaned = cleaned.replace(/^```json?\s*/i, '').replace(/\s*```$/, '');
      if (!cleaned.startsWith('{')) {
        const braceStart = cleaned.indexOf('{');
        if (braceStart >= 0) cleaned = cleaned.substring(braceStart);
      }
      const lastBrace = cleaned.lastIndexOf('}');
      if (lastBrace >= 0) cleaned = cleaned.substring(0, lastBrace + 1);
      cleaned = cleaned.replace(/,\s*}/g, '}').replace(/,\s*]/g, ']');
      const tableData = JSON.parse(cleaned);
      const headers = tableData.headers || [];
      const rows = tableData.rows || [];
      if (headers.length === 0) return match;
      const idx = tableCounter++;
      const placeholder = '{{TBL:' + idx + '}}';
      allTables.push({ index: idx, placeholder, headers, rows });
      return '\n' + placeholder + '\n';
    } catch(e) {
      return match;
    }
  });

  const mdTableRegex = /(?:^|\n)((?:\|[^\n]+\|\n)+)/g;
  const result2 = result.replace(mdTableRegex, (match, tableBlock) => {
    const lines = tableBlock.trim().split('\n').filter(l => l.trim());
    if (lines.length < 2) return match;
    const sepIdx = lines.findIndex(l => /^\|[\s\-:|]+\|$/.test(l.trim()));
    if (sepIdx < 0) return match;
    const headerLine = lines[sepIdx - 1] || lines[0];
    const headers = headerLine.split('|').filter(c => c.trim()).map(c => c.trim());
    const dataLines = lines.slice(sepIdx + 1);
    const rows = dataLines.map(l => l.split('|').filter(c => c.trim()).map(c => c.trim())).filter(r => r.length > 0);
    if (headers.length === 0 || rows.length === 0) return match;
    const idx = tableCounter++;
    const placeholder = '{{TBL:' + idx + '}}';
    allTables.push({ index: idx, placeholder, headers, rows });
    return '\n' + placeholder + '\n';
  });

  let resultClean = result2;
  resultClean = resultClean.replace(/<<<\s*TABLE\s*>>>/gi, '');
  resultClean = resultClean.replace(/<<<\s*TABLE_?END\s*>>[>}\]).]*/gi, '');
  return resultClean;
}

function findSubheadings(text, startPos) {
  const ranges = [];
  const lines = text.split('\n');
  let currentPos = startPos;
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.length >= 3 &&
        /[А-ЯЇІЄҐA-Z]/.test(trimmed) &&
        !/[а-яїієґa-z]/.test(trimmed) &&
        !trimmed.startsWith('━') &&
        !trimmed.match(/^\d+\.$/) &&
        !trimmed.startsWith('{{TBL:') &&
        trimmed.length < 60) {
      ranges.push({ start: currentPos, end: currentPos + line.length, type: 'subheading', text: trimmed });
    }
    currentPos += line.length + 1;
  }
  return ranges;
}

// ── PROCESS ALL COMPETITORS ──

const allCompetitorData = competitors.map(comp => {
  const rawSections = [
    comp.finalSummary,
    comp.sections.section1,
    comp.sections.section2,
    comp.sections.section3,
    comp.sections.section4,
    comp.sections.section5,
    comp.sections.section6
  ];
  return {
    domain: comp.domain,
    processedSections: rawSections.map(s => cleanMarkdown(extractTables(s)))
  };
});

const formatRanges = [];
let content = '';
let pos = 1;

// ═══════════════ TITLE PAGE ═══════════════

const spacer1 = '\n\n\n\n\n';
content += spacer1; pos += spacer1.length;

const mainTitle = 'SEO АУДИТ';
formatRanges.push({ start: pos, end: pos + mainTitle.length, type: 'mainTitle' });
content += mainTitle + '\n\n'; pos += mainTitle.length + 2;

if (isMulti) {
  const subtitle = 'КОНКУРЕНТНЕ СЕРЕДОВИЩЕ';
  formatRanges.push({ start: pos, end: pos + subtitle.length, type: 'domainTitle' });
  content += subtitle + '\n\n\n'; pos += subtitle.length + 3;

  for (const d of domains) {
    const domainLine = d.toUpperCase();
    formatRanges.push({ start: pos, end: pos + domainLine.length, type: 'competitorDomain' });
    content += domainLine + '\n'; pos += domainLine.length + 1;
  }
  content += '\n'; pos += 1;
} else {
  const domainTitle = domains[0].toUpperCase();
  formatRanges.push({ start: pos, end: pos + domainTitle.length, type: 'domainTitle' });
  content += domainTitle + '\n\n\n'; pos += domainTitle.length + 3;
}

const dateStr = dateToday;
formatRanges.push({ start: pos, end: pos + dateStr.length, type: 'dateText' });
content += dateStr + '\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n'; pos += dateStr.length + 15;

// ═══════════════ TABLE OF CONTENTS ═══════════════

const tocHeader = 'ЗМІСТ';
formatRanges.push({ start: pos, end: pos + tocHeader.length, type: 'tocHeader' });
content += tocHeader + '\n\n'; pos += tocHeader.length + 2;

const tocLine = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
formatRanges.push({ start: pos, end: pos + tocLine.length, type: 'tocLine' });
content += tocLine + '\n\n'; pos += tocLine.length + 2;

const sectionTitles = [
  'Executive Summary', 'Органічний трафік', 'Посилальний профіль',
  'Топ сторінки за посиланнями', 'Поведінкові метрики',
  'Ключові фрази', 'Трафікогенеруючі сторінки'
];

for (let ci = 0; ci < allCompetitorData.length; ci++) {
  if (isMulti) {
    const compTocLabel = allCompetitorData[ci].domain.toUpperCase();
    formatRanges.push({ start: pos, end: pos + compTocLabel.length, type: 'tocCompetitor' });
    content += compTocLabel + '\n'; pos += compTocLabel.length + 1;
  }
  for (let si = 0; si < sectionTitles.length; si++) {
    const num = String(si + 1).padStart(2, '0');
    const tocItemText = '     ' + num + '     ' + sectionTitles[si];
    formatRanges.push({ start: pos, end: pos + 7, type: 'tocNum' });
    content += tocItemText + '\n\n'; pos += tocItemText.length + 2;
  }
  if (isMulti && ci < allCompetitorData.length - 1) {
    content += '\n'; pos += 1;
  }
}

content += '\n\n\n\n\n\n\n\n\n\n\n\n'; pos += 12;

// ═══════════════ CONTENT SECTIONS ═══════════════

const sectionUpperTitles = [
  'EXECUTIVE SUMMARY', 'ОРГАНІЧНИЙ ТРАФІК', 'ПОСИЛАЛЬНИЙ ПРОФІЛЬ',
  'ТОП СТОРІНКИ ЗА ПОСИЛАННЯМИ', 'ПОВЕДІНКОВІ МЕТРИКИ',
  'КЛЮЧОВІ ФРАЗИ', 'ТРАФІКОГЕНЕРУЮЧІ СТОРІНКИ'
];

for (let ci = 0; ci < allCompetitorData.length; ci++) {
  const comp = allCompetitorData[ci];

  if (isMulti) {
    const sepLine = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
    formatRanges.push({ start: pos, end: pos + sepLine.length, type: 'competitorSepLine' });
    content += sepLine + '\n\n'; pos += sepLine.length + 2;

    const compHeader = comp.domain.toUpperCase();
    formatRanges.push({ start: pos, end: pos + compHeader.length, type: 'competitorHeader' });
    content += compHeader + '\n\n'; pos += compHeader.length + 2;

    const sepLine2 = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
    formatRanges.push({ start: pos, end: pos + sepLine2.length, type: 'competitorSepLine' });
    content += sepLine2 + '\n\n\n'; pos += sepLine2.length + 3;
  }

  for (let si = 0; si < sectionUpperTitles.length; si++) {
    const numText = String(si + 1).padStart(2, '0');
    formatRanges.push({ start: pos, end: pos + numText.length, type: 'sectionNum' });
    content += numText + '\n'; pos += numText.length + 1;

    const titleText = sectionUpperTitles[si];
    formatRanges.push({ start: pos, end: pos + titleText.length, type: si === 0 ? 'execTitle' : 'sectionTitle' });
    content += titleText + '\n'; pos += titleText.length + 1;

    const underline = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
    formatRanges.push({ start: pos, end: pos + underline.length, type: 'sectionLine' });
    content += underline + '\n\n'; pos += underline.length + 2;

    const sectionContent = comp.processedSections[si] + '\n\n\n\n';
    const subheadings = findSubheadings(sectionContent, pos);
    formatRanges.push(...subheadings);
    content += sectionContent; pos += sectionContent.length;
  }
}

// ═══════════════ FOOTER ═══════════════

const footerLine = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
formatRanges.push({ start: pos, end: pos + footerLine.length, type: 'footerLine' });
content += footerLine + '\n\n'; pos += footerLine.length + 2;

const footerDomains = domains.join('  •  ');
const footerText = 'Конфіденційний документ  •  ' + footerDomains + '  •  ' + dateToday;
formatRanges.push({ start: pos, end: pos + footerText.length, type: 'footerText' });
content += footerText + '\n';

const docTitle = isMulti
  ? 'SEO Аудит Конкурентів │ ' + dateToday
  : 'SEO Аудит │ ' + domains[0] + ' │ ' + dateToday;

return [{
  json: {
    domain: domains[0],
    domains,
    competitorsCount: competitors.length,
    dateToday,
    folderId,
    managerEmail,
    docTitle,
    docContent: content,
    formatRanges,
    tables: allTables
  }
}];"""

fixes = {
    "Parse Input": NEW_PARSE_INPUT,
    "Store Competitor Result": NEW_STORE_COMPETITOR_RESULT,
    "Prepare Document": NEW_PREPARE_DOCUMENT
}

fixed_count = 0
for node in wf['nodes']:
    if node['name'] in fixes:
        old_code = node['parameters'].get('jsCode', '')
        new_code = fixes[node['name']]
        node['parameters']['jsCode'] = new_code
        fixed_count += 1
        # Show diff summary
        old_has_static = '$getWorkflowStaticData' in old_code
        new_has_static = '$getWorkflowStaticData' in new_code
        print(f"  Fixed: {node['name']}")
        print(f"    staticData before: {old_has_static} → after: {new_has_static}")

print(f"\n  Total fixed: {fixed_count}/3")

# ─── Step 3: Deploy ───
print("\nStep 3: Deploying to n8n...")
payload = {
    "name": wf['name'],
    "nodes": wf['nodes'],
    "connections": wf['connections'],
    "settings": {"executionOrder": "v1"}
}

payload_json = json.dumps(payload, ensure_ascii=False)

result = subprocess.run(
    ["curl", "-s", "-X", "PUT",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}",
     "-H", f"X-N8N-API-KEY: {API_KEY}",
     "-H", "Content-Type: application/json",
     "-d", payload_json],
    capture_output=True, text=True
)

try:
    response = json.loads(result.stdout)
    if 'id' in response:
        print(f"  SUCCESS: Workflow updated (versionId: {response.get('versionId', 'N/A')[:16]}...)")
    else:
        print(f"  ERROR: {result.stdout[:500]}")
        sys.exit(1)
except json.JSONDecodeError:
    print(f"  ERROR: Invalid response: {result.stdout[:500]}")
    sys.exit(1)

# ─── Step 4: Activate ───
print("\nStep 4: Activating workflow...")
result = subprocess.run(
    ["curl", "-s", "-X", "POST",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}/activate",
     "-H", f"X-N8N-API-KEY: {API_KEY}"],
    capture_output=True, text=True
)
response = json.loads(result.stdout)
print(f"  Active: {response.get('active', 'unknown')}")

# ─── Step 5: Verify ───
print("\nStep 5: Verifying deployment...")
result = subprocess.run(
    ["curl", "-s", "-X", "GET",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}",
     "-H", f"X-N8N-API-KEY: {API_KEY}"],
    capture_output=True, text=True
)
verify_wf = json.loads(result.stdout)
for node in verify_wf['nodes']:
    if node['name'] in fixes:
        code = node['parameters'].get('jsCode', '')
        has_static = '$getWorkflowStaticData' in code
        has_all = "('.all()" in code or "').all()" in code
        print(f"  {node['name']}: staticData={has_static}, .all()={has_all}")

print("\nDone! The static data bug is fixed.")
print("Now competitor results flow through node outputs, not workflow static data.")
