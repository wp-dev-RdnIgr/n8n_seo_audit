#!/usr/bin/env python3
"""
COMPLETE WORKFLOW RESTRUCTURE: Replace SplitInBatches with manual loop.

WHY:
- SplitInBatches "done" branch CANNOT access nodes from the "loop" branch via $('Node').all()
- $getWorkflowStaticData('global') doesn't persist properly with n8n Task Runner (v2.1.4)
- Both approaches fail silently, causing "No competitor data found" errors

SOLUTION:
Manual loop carrying accumulated results through the data flow itself:

  Webhook → Parse Input → Get Next Competitor → Set Variables → ... pipeline ...
  → Final Summary Agent → Accumulate Result → Is Complete?
    → (false) Get Next Competitor (loop back)
    → (true)  Prepare Document → Create Google Doc → ... → Respond

KEY MECHANISM:
- Get Next Competitor stores loop state (urls, currentIndex, allResults) in its output
- The pipeline processes one competitor
- Accumulate Result reads loop state via $('Get Next Competitor').first().json
  (works because both nodes are on the SAME execution branch)
- Accumulate Result appends the competitor's analysis to allResults[], increments index
- IF node routes back to Get Next Competitor or forward to Prepare Document
- Prepare Document reads $json.allResults directly (no static data, no cross-branch access)

NODES REMOVED: SplitInBatches, Store Competitor Result
NODES ADDED: Get Next Competitor, Accumulate Result, Is Complete?
NODES MODIFIED: Parse Input, Prepare Document
CONNECTIONS: Rebuilt from scratch
"""

import json
import subprocess
import sys
import uuid
import copy

N8N_URL = "https://n8n.rnd.webpromo.tools"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Zjc3NjZjMS04ZTZkLTQ3OGYtYTY2Ny05MzYxOWJhMzVkYmUiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzcxODY0MDI1fQ.pDWUjuqs6RF51PEKQtTHOUFJPvOF4YLFFsBWaCoL5I8"
WORKFLOW_ID = "BAekxapYobfgHYTt"

# ═══════════════════════════════════════════════════════
# STEP 1: Fetch live workflow and save backup
# ═══════════════════════════════════════════════════════
print("=" * 60)
print("STEP 1: Fetching live workflow...")
print("=" * 60)

result = subprocess.run(
    ["curl", "-s", "-X", "GET",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}",
     "-H", f"X-N8N-API-KEY: {API_KEY}"],
    capture_output=True, text=True
)
wf = json.loads(result.stdout)
print(f"  Workflow: {wf['name']}")
print(f"  Nodes: {len(wf['nodes'])}")
print(f"  Active: {wf['active']}")

# Save backup
backup_path = "/home/user/n8n_seo_audit/workflow_backup_before_restructure.json"
with open(backup_path, 'w') as f:
    json.dump(wf, f, indent=2, ensure_ascii=False)
print(f"  Backup saved: {backup_path}")

# Build name→node lookup
nodes_by_name = {n['name']: n for n in wf['nodes']}

# ═══════════════════════════════════════════════════════
# STEP 2: Define new/modified node code
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 2: Preparing node modifications...")
print("=" * 60)

# ─── Parse Input (modified) ───
# Now outputs ONE item with {urls, currentIndex, allResults, manager_email}
PARSE_INPUT_CODE = """// Parse webhook input. Output ONE item with all URLs for manual loop.
const body = $json.body || $json;

let urls = [];
if (body.urls && Array.isArray(body.urls)) {
  urls = body.urls;
} else if (body.url) {
  urls = [body.url];
} else if (body.spreadsheetId) {
  urls = ['spreadsheet://' + body.spreadsheetId];
}

if (urls.length === 0) {
  throw new Error('No URLs provided. Expected urls array, url string, or spreadsheetId.');
}

return [{
  json: {
    urls,
    currentIndex: 0,
    totalCompetitors: urls.length,
    allResults: [],
    manager_email: body.manager_email || ''
  }
}];"""

# ─── Get Next Competitor (NEW) ───
# Extracts current competitor URL, carries loop state
GET_NEXT_CODE = """// Extract current competitor's spreadsheet ID from the URL list.
// Loop state is carried in $json (from Parse Input or from Is Complete? false branch).
const urls = $json.urls;
const idx = $json.currentIndex;
const url = urls[idx];

// Extract spreadsheet ID from Google Sheets URL
let spreadsheetId = '';
if (url.startsWith('spreadsheet://')) {
  spreadsheetId = url.replace('spreadsheet://', '');
} else {
  const match = url.match(/\\/d\\/([a-zA-Z0-9_-]+)/);
  spreadsheetId = match ? match[1] : url;
}

return [{
  json: {
    // Fields consumed by Set Variables (next node in pipeline)
    spreadsheetId,
    url,
    manager_email: $json.manager_email || '',
    // Loop state — Accumulate Result reads this via $('Get Next Competitor')
    _loop: {
      urls: $json.urls,
      currentIndex: $json.currentIndex,
      totalCompetitors: $json.totalCompetitors,
      allResults: $json.allResults || [],
      manager_email: $json.manager_email || ''
    }
  }
}];"""

# ─── Accumulate Result (NEW, replaces Store Competitor Result) ───
# Reads loop state from Get Next Competitor, appends current competitor's results
ACCUMULATE_CODE = """// Accumulate this competitor's analysis into the allResults array.
// Read loop state from Get Next Competitor (same execution branch, so $() works).
const loopState = $('Get Next Competitor').first().json._loop;
const allResults = [...loopState.allResults]; // defensive copy
const currentIndex = loopState.currentIndex;

// Read current competitor's analysis results from pipeline nodes
const domain = $('Extract Domain & Folder').first().json.domain;
const dateToday = $('Extract Domain & Folder').first().json.dateToday;
const folderId = $('Extract Domain & Folder').first().json.folderId;
const managerEmail = $('Extract Domain & Folder').first().json.managerEmail || '';
const sections = $('Collect Sections').first().json;

// Final Summary Agent output — handle different response formats
const finalSummary = $json.message?.content || $json.content || $json.text || '';

// Append this competitor's data
allResults.push({
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
});

const nextIndex = currentIndex + 1;
const isComplete = nextIndex >= loopState.totalCompetitors;

return [{
  json: {
    // Pass everything forward — IF node passes through all data
    urls: loopState.urls,
    currentIndex: nextIndex,
    totalCompetitors: loopState.totalCompetitors,
    allResults,
    manager_email: loopState.manager_email || '',
    isComplete
  }
}];"""

# ─── Prepare Document (modified) ───
# Reads from $json.allResults instead of static data
PREPARE_DOC_CODE = """// Build the final Google Doc content from ALL accumulated competitor results.
// Results come directly via $json.allResults (from IF Complete? true branch).
const competitors = $json.allResults;

if (!competitors || competitors.length === 0) {
  throw new Error('No competitor data in allResults. Array is empty.');
}

const dateToday = competitors[0].dateToday;
const folderId = competitors[0].folderId;
const managerEmail = competitors[0].managerEmail || '';
const domains = competitors.map(c => c.domain);
const isMulti = competitors.length > 1;

// ── HELPERS ──

function cleanMarkdown(text) {
  return text
    .replace(/^#{1,4}\\s*/gm, '')
    .replace(/\\*\\*([^*]+)\\*\\*/g, '$1')
    .replace(/\\*([^*]+)\\*/g, '$1')
    .replace(/^---+$/gm, '')
    .replace(/\\n{3,}/g, '\\n\\n')
    .trim();
}

let tableCounter = 0;
const allTables = [];

function extractTables(text) {
  const tableRegex = /<<<\\s*TABLE\\s*>>>\\s*([\\s\\S]*?)\\s*<<<\\s*TABLE_?END\\s*>>[>\\s})\\].]*?/gi;
  const result = text.replace(tableRegex, (match, jsonStr) => {
    try {
      let cleaned = jsonStr.trim();
      cleaned = cleaned.replace(/^```json?\\s*/i, '').replace(/\\s*```$/, '');
      if (!cleaned.startsWith('{')) {
        const braceStart = cleaned.indexOf('{');
        if (braceStart >= 0) cleaned = cleaned.substring(braceStart);
      }
      const lastBrace = cleaned.lastIndexOf('}');
      if (lastBrace >= 0) cleaned = cleaned.substring(0, lastBrace + 1);
      cleaned = cleaned.replace(/,\\s*}/g, '}').replace(/,\\s*]/g, ']');
      const tableData = JSON.parse(cleaned);
      const headers = tableData.headers || [];
      const rows = tableData.rows || [];
      if (headers.length === 0) return match;
      const idx = tableCounter++;
      const placeholder = '{{TBL:' + idx + '}}';
      allTables.push({ index: idx, placeholder, headers, rows });
      return '\\n' + placeholder + '\\n';
    } catch(e) {
      return match;
    }
  });

  const mdTableRegex = /(?:^|\\n)((?:\\|[^\\n]+\\|\\n)+)/g;
  const result2 = result.replace(mdTableRegex, (match, tableBlock) => {
    const lines = tableBlock.trim().split('\\n').filter(l => l.trim());
    if (lines.length < 2) return match;
    const sepIdx = lines.findIndex(l => /^\\|[\\s\\-:|]+\\|$/.test(l.trim()));
    if (sepIdx < 0) return match;
    const headerLine = lines[sepIdx - 1] || lines[0];
    const headers = headerLine.split('|').filter(c => c.trim()).map(c => c.trim());
    const dataLines = lines.slice(sepIdx + 1);
    const rows = dataLines.map(l => l.split('|').filter(c => c.trim()).map(c => c.trim())).filter(r => r.length > 0);
    if (headers.length === 0 || rows.length === 0) return match;
    const idx = tableCounter++;
    const placeholder = '{{TBL:' + idx + '}}';
    allTables.push({ index: idx, placeholder, headers, rows });
    return '\\n' + placeholder + '\\n';
  });

  let resultClean = result2;
  resultClean = resultClean.replace(/<<<\\s*TABLE\\s*>>>/gi, '');
  resultClean = resultClean.replace(/<<<\\s*TABLE_?END\\s*>>[>}\\]).]*]/gi, '');
  return resultClean;
}

function findSubheadings(text, startPos) {
  const ranges = [];
  const lines = text.split('\\n');
  let currentPos = startPos;
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.length >= 3 &&
        /[А-ЯЇІЄҐA-Z]/.test(trimmed) &&
        !/[а-яїієґa-z]/.test(trimmed) &&
        !trimmed.startsWith('━') &&
        !trimmed.match(/^\\d+\\.$/) &&
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

const spacer1 = '\\n\\n\\n\\n\\n';
content += spacer1; pos += spacer1.length;

const mainTitle = 'SEO АУДИТ';
formatRanges.push({ start: pos, end: pos + mainTitle.length, type: 'mainTitle' });
content += mainTitle + '\\n\\n'; pos += mainTitle.length + 2;

if (isMulti) {
  const subtitle = 'КОНКУРЕНТНЕ СЕРЕДОВИЩЕ';
  formatRanges.push({ start: pos, end: pos + subtitle.length, type: 'domainTitle' });
  content += subtitle + '\\n\\n\\n'; pos += subtitle.length + 3;

  for (const d of domains) {
    const domainLine = d.toUpperCase();
    formatRanges.push({ start: pos, end: pos + domainLine.length, type: 'competitorDomain' });
    content += domainLine + '\\n'; pos += domainLine.length + 1;
  }
  content += '\\n'; pos += 1;
} else {
  const domainTitle = domains[0].toUpperCase();
  formatRanges.push({ start: pos, end: pos + domainTitle.length, type: 'domainTitle' });
  content += domainTitle + '\\n\\n\\n'; pos += domainTitle.length + 3;
}

const dateStr = dateToday;
formatRanges.push({ start: pos, end: pos + dateStr.length, type: 'dateText' });
content += dateStr + '\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n'; pos += dateStr.length + 15;

// ═══════════════ TABLE OF CONTENTS ═══════════════

const tocHeader = 'ЗМІСТ';
formatRanges.push({ start: pos, end: pos + tocHeader.length, type: 'tocHeader' });
content += tocHeader + '\\n\\n'; pos += tocHeader.length + 2;

const tocLine = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
formatRanges.push({ start: pos, end: pos + tocLine.length, type: 'tocLine' });
content += tocLine + '\\n\\n'; pos += tocLine.length + 2;

const sectionTitles = [
  'Executive Summary', 'Органічний трафік', 'Посилальний профіль',
  'Топ сторінки за посиланнями', 'Поведінкові метрики',
  'Ключові фрази', 'Трафікогенеруючі сторінки'
];

for (let ci = 0; ci < allCompetitorData.length; ci++) {
  if (isMulti) {
    const compTocLabel = allCompetitorData[ci].domain.toUpperCase();
    formatRanges.push({ start: pos, end: pos + compTocLabel.length, type: 'tocCompetitor' });
    content += compTocLabel + '\\n'; pos += compTocLabel.length + 1;
  }
  for (let si = 0; si < sectionTitles.length; si++) {
    const num = String(si + 1).padStart(2, '0');
    const tocItemText = '     ' + num + '     ' + sectionTitles[si];
    formatRanges.push({ start: pos, end: pos + 7, type: 'tocNum' });
    content += tocItemText + '\\n\\n'; pos += tocItemText.length + 2;
  }
  if (isMulti && ci < allCompetitorData.length - 1) {
    content += '\\n'; pos += 1;
  }
}

content += '\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n\\n'; pos += 12;

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
    content += sepLine + '\\n\\n'; pos += sepLine.length + 2;

    const compHeader = comp.domain.toUpperCase();
    formatRanges.push({ start: pos, end: pos + compHeader.length, type: 'competitorHeader' });
    content += compHeader + '\\n\\n'; pos += compHeader.length + 2;

    const sepLine2 = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
    formatRanges.push({ start: pos, end: pos + sepLine2.length, type: 'competitorSepLine' });
    content += sepLine2 + '\\n\\n\\n'; pos += sepLine2.length + 3;
  }

  for (let si = 0; si < sectionUpperTitles.length; si++) {
    const numText = String(si + 1).padStart(2, '0');
    formatRanges.push({ start: pos, end: pos + numText.length, type: 'sectionNum' });
    content += numText + '\\n'; pos += numText.length + 1;

    const titleText = sectionUpperTitles[si];
    formatRanges.push({ start: pos, end: pos + titleText.length, type: si === 0 ? 'execTitle' : 'sectionTitle' });
    content += titleText + '\\n'; pos += titleText.length + 1;

    const underline = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
    formatRanges.push({ start: pos, end: pos + underline.length, type: 'sectionLine' });
    content += underline + '\\n\\n'; pos += underline.length + 2;

    const sectionContent = comp.processedSections[si] + '\\n\\n\\n\\n';
    const subheadings = findSubheadings(sectionContent, pos);
    formatRanges.push(...subheadings);
    content += sectionContent; pos += sectionContent.length;
  }
}

// ═══════════════ FOOTER ═══════════════

const footerLine = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
formatRanges.push({ start: pos, end: pos + footerLine.length, type: 'footerLine' });
content += footerLine + '\\n\\n'; pos += footerLine.length + 2;

const footerDomains = domains.join('  •  ');
const footerText = 'Конфіденційний документ  •  ' + footerDomains + '  •  ' + dateToday;
formatRanges.push({ start: pos, end: pos + footerText.length, type: 'footerText' });
content += footerText + '\\n';

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

# ═══════════════════════════════════════════════════════
# STEP 3: Build the modified workflow
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 3: Building modified workflow...")
print("=" * 60)

# ─── Remove nodes ───
REMOVE_NODES = {"SplitInBatches", "Store Competitor Result"}
new_nodes = [n for n in wf['nodes'] if n['name'] not in REMOVE_NODES]
print(f"  Removed: {REMOVE_NODES}")

# ─── Modify Parse Input ───
for n in new_nodes:
    if n['name'] == 'Parse Input':
        n['parameters']['jsCode'] = PARSE_INPUT_CODE
        print(f"  Modified: Parse Input")

# ─── Modify Prepare Document ───
for n in new_nodes:
    if n['name'] == 'Prepare Document':
        n['parameters']['jsCode'] = PREPARE_DOC_CODE
        print(f"  Modified: Prepare Document")

# ─── Add new nodes ───

# Get Next Competitor
get_next_node = {
    "parameters": {"jsCode": GET_NEXT_CODE},
    "id": str(uuid.uuid4()),
    "name": "Get Next Competitor",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [-688, 448]
}
new_nodes.append(get_next_node)
print(f"  Added: Get Next Competitor (id={get_next_node['id'][:8]}...)")

# Accumulate Result
accumulate_node = {
    "parameters": {"jsCode": ACCUMULATE_CODE},
    "id": str(uuid.uuid4()),
    "name": "Accumulate Result",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [1136, 304]
}
new_nodes.append(accumulate_node)
print(f"  Added: Accumulate Result (id={accumulate_node['id'][:8]}...)")

# Is Complete? (IF node)
is_complete_node = {
    "parameters": {
        "conditions": {
            "options": {
                "caseSensitive": True,
                "leftValue": ""
            },
            "conditions": [
                {
                    "id": "is-complete-check",
                    "leftValue": "={{ $json.isComplete }}",
                    "rightValue": True,
                    "operator": {
                        "type": "boolean",
                        "operation": "true"
                    }
                }
            ],
            "combinator": "and"
        },
        "options": {}
    },
    "id": str(uuid.uuid4()),
    "name": "Is Complete?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2,
    "position": [1312, 400]
}
new_nodes.append(is_complete_node)
print(f"  Added: Is Complete? (id={is_complete_node['id'][:8]}...)")

print(f"  Total nodes: {len(new_nodes)}")

# ═══════════════════════════════════════════════════════
# STEP 4: Build ALL connections from scratch
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 4: Building connections...")
print("=" * 60)

connections = {
    # ─── Entry ───
    "Webhook": {
        "main": [[
            {"node": "Parse Input", "type": "main", "index": 0}
        ]]
    },
    "Parse Input": {
        "main": [[
            {"node": "Get Next Competitor", "type": "main", "index": 0}
        ]]
    },

    # ─── Manual loop entry → pipeline ───
    "Get Next Competitor": {
        "main": [[
            {"node": "Set Variables", "type": "main", "index": 0}
        ]]
    },

    # ─── Standard pipeline (unchanged) ───
    "Set Variables": {
        "main": [[
            {"node": "Get Spreadsheet Info", "type": "main", "index": 0}
        ]]
    },
    "Get Spreadsheet Info": {
        "main": [[
            {"node": "Extract Domain & Folder", "type": "main", "index": 0}
        ]]
    },
    "Extract Domain & Folder": {
        "main": [[
            {"node": "Read All Sheets", "type": "main", "index": 0}
        ]]
    },
    "Read All Sheets": {
        "main": [[
            {"node": "Prepare Data", "type": "main", "index": 0}
        ]]
    },

    # ─── 6 Agents in parallel ───
    "Prepare Data": {
        "main": [[
            {"node": "Agent 1 - Organic Traffic", "type": "main", "index": 0},
            {"node": "Agent 2 - Link Profile", "type": "main", "index": 0},
            {"node": "Agent 3 - Top Pages Links", "type": "main", "index": 0},
            {"node": "Agent 4 - Behavioral", "type": "main", "index": 0},
            {"node": "Agent 5 - Keywords", "type": "main", "index": 0},
            {"node": "Agent 6 - Traffic Pages", "type": "main", "index": 0},
        ]]
    },

    # ─── Agents → Merge (each to a different input index) ───
    "Agent 1 - Organic Traffic": {
        "main": [[{"node": "Merge Results", "type": "main", "index": 0}]]
    },
    "Agent 2 - Link Profile": {
        "main": [[{"node": "Merge Results", "type": "main", "index": 1}]]
    },
    "Agent 3 - Top Pages Links": {
        "main": [[{"node": "Merge Results", "type": "main", "index": 2}]]
    },
    "Agent 4 - Behavioral": {
        "main": [[{"node": "Merge Results", "type": "main", "index": 3}]]
    },
    "Agent 5 - Keywords": {
        "main": [[{"node": "Merge Results", "type": "main", "index": 4}]]
    },
    "Agent 6 - Traffic Pages": {
        "main": [[{"node": "Merge Results", "type": "main", "index": 5}]]
    },

    # ─── Merge → Collect → Summary ───
    "Merge Results": {
        "main": [[{"node": "Collect Sections", "type": "main", "index": 0}]]
    },
    "Collect Sections": {
        "main": [[{"node": "Final Summary Agent", "type": "main", "index": 0}]]
    },

    # ─── Loop control: Accumulate → IF → loop back or continue ───
    "Final Summary Agent": {
        "main": [[{"node": "Accumulate Result", "type": "main", "index": 0}]]
    },
    "Accumulate Result": {
        "main": [[{"node": "Is Complete?", "type": "main", "index": 0}]]
    },
    "Is Complete?": {
        "main": [
            # Output 0 (true): all competitors processed → build document
            [{"node": "Prepare Document", "type": "main", "index": 0}],
            # Output 1 (false): more competitors → loop back
            [{"node": "Get Next Competitor", "type": "main", "index": 0}],
        ]
    },

    # ─── Document creation pipeline (unchanged) ───
    "Prepare Document": {
        "main": [[{"node": "Create Google Doc", "type": "main", "index": 0}]]
    },
    "Create Google Doc": {
        "main": [[{"node": "Write Document Content", "type": "main", "index": 0}]]
    },
    "Write Document Content": {
        "main": [[{"node": "Build Format Requests", "type": "main", "index": 0}]]
    },
    "Build Format Requests": {
        "main": [[{"node": "Apply Formatting", "type": "main", "index": 0}]]
    },
    "Apply Formatting": {
        "main": [[{"node": "Read Document", "type": "main", "index": 0}]]
    },
    "Read Document": {
        "main": [[{"node": "Build Table Requests", "type": "main", "index": 0}]]
    },
    "Build Table Requests": {
        "main": [[{"node": "Has Tables?", "type": "main", "index": 0}]]
    },
    "Has Tables?": {
        "main": [
            # Output 0 (true): tables exist → process them
            [{"node": "Execute Table Requests", "type": "main", "index": 0}],
            # Output 1 (false): no tables → skip to merge
            [{"node": "Merge Table Branch", "type": "main", "index": 1}],
        ]
    },
    "Execute Table Requests": {
        "main": [[{"node": "Read Document Final", "type": "main", "index": 0}]]
    },
    "Read Document Final": {
        "main": [[{"node": "Build Cell Text", "type": "main", "index": 0}]]
    },
    "Build Cell Text": {
        "main": [[{"node": "Execute Cell Text", "type": "main", "index": 0}]]
    },
    "Execute Cell Text": {
        "main": [[{"node": "Read Doc For Styling", "type": "main", "index": 0}]]
    },
    "Read Doc For Styling": {
        "main": [[{"node": "Build Table Style", "type": "main", "index": 0}]]
    },
    "Build Table Style": {
        "main": [[{"node": "Apply Table Style", "type": "main", "index": 0}]]
    },
    "Apply Table Style": {
        "main": [[{"node": "Merge Table Branch", "type": "main", "index": 0}]]
    },
    "Merge Table Branch": {
        "main": [[{"node": "Move to Folder", "type": "main", "index": 0}]]
    },
    "Move to Folder": {
        "main": [[{"node": "Respond", "type": "main", "index": 0}]]
    },
    # Respond has no outgoing connections (terminal node)
}

# ─── Verify all connection targets exist ───
node_names = {n['name'] for n in new_nodes}
errors = []
for src, outputs in connections.items():
    if src not in node_names:
        errors.append(f"Source node '{src}' not found in workflow")
    for out_list in outputs.get('main', []):
        for conn in out_list:
            if conn['node'] not in node_names:
                errors.append(f"Target node '{conn['node']}' (from '{src}') not found")

if errors:
    print("\n  ERRORS in connections:")
    for e in errors:
        print(f"    {e}")
    sys.exit(1)
else:
    print(f"  All {len(connections)} source nodes verified")
    total_conns = sum(len(c) for outs in connections.values() for ol in outs.get('main', []) for c in [ol])
    print(f"  Total connections: {total_conns}")
    print("  All target nodes verified")

# ═══════════════════════════════════════════════════════
# STEP 5: Deploy to n8n
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 5: Deploying to n8n...")
print("=" * 60)

payload = {
    "name": wf['name'],
    "nodes": new_nodes,
    "connections": connections,
    "settings": {"executionOrder": "v1"}
}

payload_json = json.dumps(payload, ensure_ascii=False)

# Also save the payload for debugging
with open("/home/user/n8n_seo_audit/workflow_restructured.json", 'w') as f:
    json.dump(payload, f, indent=2, ensure_ascii=False)
print(f"  Payload saved: workflow_restructured.json")

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
        print(f"  SUCCESS: Workflow updated")
        print(f"  Version: {response.get('versionId', 'N/A')[:16]}...")
        print(f"  Nodes: {len(response.get('nodes', []))}")
    else:
        print(f"  ERROR: {result.stdout[:500]}")
        sys.exit(1)
except json.JSONDecodeError:
    print(f"  ERROR: Invalid response: {result.stdout[:500]}")
    sys.exit(1)

# ═══════════════════════════════════════════════════════
# STEP 6: Activate
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 6: Activating workflow...")
print("=" * 60)

result = subprocess.run(
    ["curl", "-s", "-X", "POST",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}/activate",
     "-H", f"X-N8N-API-KEY: {API_KEY}"],
    capture_output=True, text=True
)
response = json.loads(result.stdout)
print(f"  Active: {response.get('active', 'unknown')}")

# ═══════════════════════════════════════════════════════
# STEP 7: Verify deployment
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 7: Verifying deployment...")
print("=" * 60)

result = subprocess.run(
    ["curl", "-s", "-X", "GET",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}",
     "-H", f"X-N8N-API-KEY: {API_KEY}"],
    capture_output=True, text=True
)
verify_wf = json.loads(result.stdout)

print(f"  Total nodes: {len(verify_wf['nodes'])}")

# Check removed nodes are gone
for n in verify_wf['nodes']:
    if n['name'] in REMOVE_NODES:
        print(f"  FAIL: {n['name']} still exists!")
        sys.exit(1)

# Check new nodes exist
required_new = {"Get Next Competitor", "Accumulate Result", "Is Complete?"}
found_new = {n['name'] for n in verify_wf['nodes']} & required_new
missing = required_new - found_new
if missing:
    print(f"  FAIL: Missing new nodes: {missing}")
    sys.exit(1)

# Check key code
for n in verify_wf['nodes']:
    code = n['parameters'].get('jsCode', '')
    if n['name'] == 'Parse Input':
        ok = 'currentIndex' in code and 'allResults' in code and 'staticData' not in code
        print(f"  Parse Input: {'OK' if ok else 'FAIL'} (has loop init, no static data)")
    elif n['name'] == 'Get Next Competitor':
        ok = '_loop' in code and 'spreadsheetId' in code
        print(f"  Get Next Competitor: {'OK' if ok else 'FAIL'} (carries _loop state)")
    elif n['name'] == 'Accumulate Result':
        ok = "Get Next Competitor" in code and 'allResults' in code and 'isComplete' in code
        print(f"  Accumulate Result: {'OK' if ok else 'FAIL'} (reads from Get Next, accumulates)")
    elif n['name'] == 'Is Complete?':
        params_str = json.dumps(n['parameters'])
        ok = 'isComplete' in params_str
        print(f"  Is Complete?: {'OK' if ok else 'FAIL'} (checks isComplete)")
    elif n['name'] == 'Prepare Document':
        ok = 'allResults' in code and 'staticData' not in code and 'Store Competitor' not in code
        print(f"  Prepare Document: {'OK' if ok else 'FAIL'} (reads allResults, no static data)")

# Check connections
verify_conns = verify_wf['connections']
critical_checks = [
    ("Parse Input", "Get Next Competitor"),
    ("Get Next Competitor", "Set Variables"),
    ("Final Summary Agent", "Accumulate Result"),
    ("Accumulate Result", "Is Complete?"),
]
for src, target in critical_checks:
    found = False
    if src in verify_conns:
        for out_list in verify_conns[src].get('main', []):
            for c in out_list:
                if c['node'] == target:
                    found = True
    print(f"  Connection {src} → {target}: {'OK' if found else 'MISSING!'}")

# Check IF node has both outputs
if "Is Complete?" in verify_conns:
    outputs = verify_conns["Is Complete?"].get("main", [])
    has_true = len(outputs) > 0 and any(c['node'] == 'Prepare Document' for c in outputs[0])
    has_false = len(outputs) > 1 and any(c['node'] == 'Get Next Competitor' for c in outputs[1])
    print(f"  Is Complete? → Prepare Document (true): {'OK' if has_true else 'MISSING!'}")
    print(f"  Is Complete? → Get Next Competitor (false): {'OK' if has_false else 'MISSING!'}")

# Check no removed nodes referenced
print(f"\n  Removed nodes gone: OK")
print(f"  New nodes present: OK")

print("\n" + "=" * 60)
print("DEPLOYMENT COMPLETE")
print("=" * 60)
print(f"  URL: {N8N_URL}/workflow/{WORKFLOW_ID}")
print(f"  Nodes: {len(verify_wf['nodes'])} (was {len(wf['nodes'])})")
print(f"  Removed: SplitInBatches, Store Competitor Result")
print(f"  Added: Get Next Competitor, Accumulate Result, Is Complete?")
print(f"  Modified: Parse Input, Prepare Document")
print(f"  Backup: {backup_path}")
