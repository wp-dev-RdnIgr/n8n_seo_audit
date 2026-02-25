#!/usr/bin/env python3
"""Modify SEO_Audit_AI_Report.json to support real Google Docs tables."""

import json
import copy

with open('/home/user/n8n_seo_audit/SEO_Audit_AI_Report.json', 'r') as f:
    wf = json.load(f)

# ═══════════════════════════════════════════════════════════════
# 1. MODIFY AGENT PROMPTS — add table format instructions
# ═══════════════════════════════════════════════════════════════

TABLE_INSTRUCTION = (
    "• Коли потрібно подати структуровані дані (метрики, порівняння, рейтинги, розподіли) "
    "у табличному вигляді, обов'язково використовуй спеціальний формат:\n\n"
    "<<<TABLE>>>\n"
    '{\"headers\": [\"Колонка 1\", \"Колонка 2\"], \"rows\": [[\"знач1\", \"знач2\"], [\"знач3\", \"знач4\"]]}\n'
    "<<<TABLE_END>>>\n\n"
    "Таблиця автоматично відформатується у Google Doc. Використовуй таблиці для: "
    "топ-списків з числовими показниками, порівняльних даних, розподілів по категоріях, метрик.\n"
    "• НЕ використовуй markdown-таблиці (|---|)"
)

OLD_TABLE_LINE = "• НЕ використовуй markdown-таблиці (|---|)"

for node in wf['nodes']:
    if node.get('name', '').startswith('Agent') or node.get('name', '') == 'Final Summary Agent':
        try:
            content = node['parameters']['messages']['values'][0]['content']
            if OLD_TABLE_LINE in content:
                content = content.replace(OLD_TABLE_LINE, TABLE_INSTRUCTION)
                node['parameters']['messages']['values'][0]['content'] = content
                print(f"  Updated prompt: {node['name']}")
        except (KeyError, IndexError):
            pass

# ═══════════════════════════════════════════════════════════════
# 2. MODIFY "Prepare Document" — extract tables, create placeholders
# ═══════════════════════════════════════════════════════════════

PREPARE_DOC_CODE = r"""const domain = $('Extract Domain & Folder').first().json.domain;
const dateToday = $('Extract Domain & Folder').first().json.dateToday || $('Extract Domain & Folder').first().json.date_today;
const folderId = $('Extract Domain & Folder').first().json.folderId;

const section1 = $('Collect Sections').first().json.section1 || '';
const section2 = $('Collect Sections').first().json.section2 || '';
const section3 = $('Collect Sections').first().json.section3 || '';
const section4 = $('Collect Sections').first().json.section4 || '';
const section5 = $('Collect Sections').first().json.section5 || '';
const section6 = $('Collect Sections').first().json.section6 || '';
const finalSummary = $json.message?.content || $json.content || $json.text || '';

function cleanMarkdown(text) {
  return text
    .replace(/^#{1,4}\s*/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/^---+$/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

// ── TABLE EXTRACTION ──
// Global table counter across all sections
let tableCounter = 0;
const allTables = [];

function extractTables(text) {
  const tableRegex = /<<<TABLE>>>\s*([\s\S]*?)\s*<<<TABLE_END>>>/g;
  const result = text.replace(tableRegex, (match, jsonStr) => {
    try {
      // Clean the JSON string (remove potential markdown artifacts)
      let cleaned = jsonStr.trim();
      // Try to fix common JSON issues from LLM output
      if (!cleaned.startsWith('{')) {
        const braceStart = cleaned.indexOf('{');
        if (braceStart >= 0) cleaned = cleaned.substring(braceStart);
      }
      const lastBrace = cleaned.lastIndexOf('}');
      if (lastBrace >= 0) cleaned = cleaned.substring(0, lastBrace + 1);

      const tableData = JSON.parse(cleaned);
      const headers = tableData.headers || [];
      const rows = tableData.rows || [];

      if (headers.length === 0) return match; // Invalid table

      const idx = tableCounter++;
      const placeholder = '{{TBL:' + idx + '}}';
      allTables.push({
        index: idx,
        placeholder: placeholder,
        headers: headers,
        rows: rows
      });
      return '\n' + placeholder + '\n';
    } catch(e) {
      // If JSON parsing fails, also try to catch markdown tables that slipped through
      return match;
    }
  });

  // Also catch markdown tables (|---|) and convert them
  const mdTableRegex = /(?:^|\n)((?:\|[^\n]+\|\n)+)/g;
  const result2 = result.replace(mdTableRegex, (match, tableBlock) => {
    const lines = tableBlock.trim().split('\n').filter(l => l.trim());
    if (lines.length < 2) return match;

    // Check if second line is a separator (|---|---|)
    const sepIdx = lines.findIndex(l => /^\|[\s\-:|]+\|$/.test(l.trim()));
    if (sepIdx < 0) return match;

    const headerLine = lines[sepIdx - 1] || lines[0];
    const headers = headerLine.split('|').filter(c => c.trim()).map(c => c.trim());
    const dataLines = lines.slice(sepIdx + 1);
    const rows = dataLines.map(l =>
      l.split('|').filter(c => c.trim()).map(c => c.trim())
    ).filter(r => r.length > 0);

    if (headers.length === 0 || rows.length === 0) return match;

    const idx = tableCounter++;
    const placeholder = '{{TBL:' + idx + '}}';
    allTables.push({
      index: idx,
      placeholder: placeholder,
      headers: headers,
      rows: rows
    });
    return '\n' + placeholder + '\n';
  });

  return result2;
}

// ── SUBHEADING DETECTION ──
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
      ranges.push({
        start: currentPos,
        end: currentPos + line.length,
        type: 'subheading',
        text: trimmed
      });
    }
    currentPos += line.length + 1;
  }
  return ranges;
}

// ── PROCESS SECTIONS — extract tables BEFORE cleaning markdown ──
const rawSections = [finalSummary, section1, section2, section3, section4, section5, section6];
const processedSections = rawSections.map(s => cleanMarkdown(extractTables(s)));

const formatRanges = [];
let content = '';
let pos = 1;

// ══════════════════════════════════════════════════════════════
// TITLE PAGE
// ══════════════════════════════════════════════════════════════

const spacer1 = '\n\n\n\n\n';
content += spacer1; pos += spacer1.length;

const mainTitle = 'SEO АУДИТ';
formatRanges.push({ start: pos, end: pos + mainTitle.length, type: 'mainTitle' });
content += mainTitle + '\n\n'; pos += mainTitle.length + 2;

const domainTitle = domain.toUpperCase();
formatRanges.push({ start: pos, end: pos + domainTitle.length, type: 'domainTitle' });
content += domainTitle + '\n\n\n'; pos += domainTitle.length + 3;

const dateStr = dateToday;
formatRanges.push({ start: pos, end: pos + dateStr.length, type: 'dateText' });
content += dateStr + '\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n'; pos += dateStr.length + 15;

// ══════════════════════════════════════════════════════════════
// TABLE OF CONTENTS
// ══════════════════════════════════════════════════════════════

const tocHeader = 'ЗМІСТ';
formatRanges.push({ start: pos, end: pos + tocHeader.length, type: 'tocHeader' });
content += tocHeader + '\n\n'; pos += tocHeader.length + 2;

const tocLine = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
formatRanges.push({ start: pos, end: pos + tocLine.length, type: 'tocLine' });
content += tocLine + '\n\n'; pos += tocLine.length + 2;

const tocItems = [
  { num: '01', title: 'Executive Summary' },
  { num: '02', title: 'Органічний трафік' },
  { num: '03', title: 'Посилальний профіль' },
  { num: '04', title: 'Топ сторінки за посиланнями' },
  { num: '05', title: 'Поведінкові метрики' },
  { num: '06', title: 'Ключові фрази' },
  { num: '07', title: 'Трафікогенеруючі сторінки' }
];

for (const item of tocItems) {
  const tocItemText = `     ${item.num}     ${item.title}`;
  formatRanges.push({ start: pos, end: pos + 7, type: 'tocNum' });
  content += tocItemText + '\n\n'; pos += tocItemText.length + 2;
}

content += '\n\n\n\n\n\n\n\n\n\n\n\n'; pos += 12;

// ══════════════════════════════════════════════════════════════
// SECTIONS
// ══════════════════════════════════════════════════════════════

const sections = [
  { num: '01', title: 'EXECUTIVE SUMMARY', content: processedSections[0], isExec: true },
  { num: '02', title: 'ОРГАНІЧНИЙ ТРАФІК', content: processedSections[1] },
  { num: '03', title: 'ПОСИЛАЛЬНИЙ ПРОФІЛЬ', content: processedSections[2] },
  { num: '04', title: 'ТОП СТОРІНКИ ЗА ПОСИЛАННЯМИ', content: processedSections[3] },
  { num: '05', title: 'ПОВЕДІНКОВІ МЕТРИКИ', content: processedSections[4] },
  { num: '06', title: 'КЛЮЧОВІ ФРАЗИ', content: processedSections[5] },
  { num: '07', title: 'ТРАФІКОГЕНЕРУЮЧІ СТОРІНКИ', content: processedSections[6] }
];

for (const section of sections) {
  const numText = section.num;
  formatRanges.push({ start: pos, end: pos + numText.length, type: 'sectionNum' });
  content += numText + '\n'; pos += numText.length + 1;

  const titleText = section.title;
  formatRanges.push({ start: pos, end: pos + titleText.length, type: section.isExec ? 'execTitle' : 'sectionTitle' });
  content += titleText + '\n'; pos += titleText.length + 1;

  const underline = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
  formatRanges.push({ start: pos, end: pos + underline.length, type: 'sectionLine' });
  content += underline + '\n\n'; pos += underline.length + 2;

  const sectionContent = section.content + '\n\n\n\n';
  const subheadings = findSubheadings(sectionContent, pos);
  formatRanges.push(...subheadings);

  content += sectionContent; pos += sectionContent.length;
}

// ══════════════════════════════════════════════════════════════
// FOOTER
// ══════════════════════════════════════════════════════════════

const footerLine = '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
formatRanges.push({ start: pos, end: pos + footerLine.length, type: 'footerLine' });
content += footerLine + '\n\n'; pos += footerLine.length + 2;

const footerText = `Конфіденційний документ  •  ${domain}  •  ${dateToday}`;
formatRanges.push({ start: pos, end: pos + footerText.length, type: 'footerText' });
content += footerText + '\n';

return [{
  json: {
    domain,
    dateToday,
    folderId,
    docTitle: `SEO Аудит │ ${domain} │ ${dateToday}`,
    docContent: content,
    formatRanges,
    tables: allTables
  }
}];"""

# Find and update the Prepare Document node
for node in wf['nodes']:
    if node.get('id') == 'node-prepare-doc':
        node['parameters']['jsCode'] = PREPARE_DOC_CODE
        print("  Updated: Prepare Document node")
        break

# ═══════════════════════════════════════════════════════════════
# 3. ADD NEW NODES for table insertion & formatting
# ═══════════════════════════════════════════════════════════════

# Node: Read Document (after Apply Formatting)
node_read_doc = {
    "parameters": {
        "method": "GET",
        "url": "=https://docs.googleapis.com/v1/documents/{{ $('Create Google Doc').first().json.documentId }}",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "googleDocsOAuth2Api",
        "options": {}
    },
    "id": "node-read-doc",
    "name": "Read Document",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.3,
    "position": [2300, 300],
    "credentials": {
        "googleDocsOAuth2Api": {
            "id": "google-docs-credentials",
            "name": "Google Docs"
        }
    }
}

# Node: Build Table Requests (Code)
BUILD_TABLE_REQUESTS_CODE = r"""const docId = $('Create Google Doc').first().json.documentId;
const docBody = $json.body;
const tables = $('Prepare Document').first().json.tables || [];

if (!tables.length || !docBody || !docBody.content) {
  return [{ json: { docId, requests: [], hasTables: false } }];
}

// Find placeholder positions in document
const placeholders = [];

for (const elem of docBody.content) {
  if (elem.paragraph && elem.paragraph.elements) {
    for (const el of elem.paragraph.elements) {
      if (el.textRun && el.textRun.content) {
        const text = el.textRun.content;
        const regex = /\{\{TBL:(\d+)\}\}/g;
        let match;
        while ((match = regex.exec(text)) !== null) {
          const tableIdx = parseInt(match[1]);
          placeholders.push({
            tableIdx,
            startIndex: el.startIndex + match.index,
            endIndex: el.startIndex + match.index + match[0].length,
            paraStartIndex: elem.startIndex,
            paraEndIndex: elem.endIndex
          });
        }
      }
    }
  }
}

if (!placeholders.length) {
  return [{ json: { docId, requests: [], hasTables: false } }];
}

// Sort from last to first (by position, descending)
placeholders.sort((a, b) => b.startIndex - a.startIndex);

const requests = [];

// Track table positions for later formatting
const tablePositions = [];

for (const ph of placeholders) {
  const table = tables.find(t => t.index === ph.tableIdx);
  if (!table) continue;

  const totalRows = 1 + table.rows.length; // header + data rows
  const totalCols = table.headers.length;

  if (totalCols === 0) continue;

  // 1. Delete the entire paragraph containing the placeholder
  // (includes the placeholder text and its newline)
  requests.push({
    deleteContentRange: {
      range: {
        startIndex: ph.paraStartIndex,
        endIndex: ph.paraEndIndex
      }
    }
  });

  // 2. Insert table at the paragraph start position
  const tableInsertPos = ph.paraStartIndex;
  requests.push({
    insertTable: {
      rows: totalRows,
      columns: totalCols,
      location: {
        index: tableInsertPos
      }
    }
  });

  // 3. Populate cells from LAST to FIRST
  // For a newly inserted empty table at index S with C columns:
  // Cell(r, c) text insertion index = S + 4 + r * (1 + 3 * C) + c * 3
  const allCells = [];

  // Header row (row 0)
  for (let c = 0; c < totalCols; c++) {
    allCells.push({ r: 0, c: c, text: String(table.headers[c] || '') });
  }
  // Data rows
  for (let r = 0; r < table.rows.length; r++) {
    for (let c = 0; c < totalCols; c++) {
      allCells.push({ r: r + 1, c: c, text: String(table.rows[r]?.[c] ?? '') });
    }
  }

  // Sort from last cell to first cell
  allCells.sort((a, b) => {
    if (a.r !== b.r) return b.r - a.r;
    return b.c - a.c;
  });

  for (const cell of allCells) {
    if (cell.text) {
      const cellIndex = tableInsertPos + 4 + cell.r * (1 + 3 * totalCols) + cell.c * 3;
      requests.push({
        insertText: {
          location: { index: cellIndex },
          text: cell.text
        }
      });
    }
  }

  tablePositions.push({
    insertPos: tableInsertPos,
    totalRows,
    totalCols,
    headers: table.headers,
    rows: table.rows
  });
}

return [{ json: { docId, requests, hasTables: true, tablePositions } }];"""

node_build_table_requests = {
    "parameters": {
        "jsCode": BUILD_TABLE_REQUESTS_CODE
    },
    "id": "node-build-table-req",
    "name": "Build Table Requests",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [2500, 300]
}

# Node: Execute Table Requests (HTTP batchUpdate) — conditional
node_exec_table_requests = {
    "parameters": {
        "method": "POST",
        "url": "=https://docs.googleapis.com/v1/documents/{{ $json.docId }}:batchUpdate",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "googleDocsOAuth2Api",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ requests: $json.requests }) }}",
        "options": {}
    },
    "id": "node-exec-table-req",
    "name": "Execute Table Requests",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.3,
    "position": [2700, 200],
    "credentials": {
        "googleDocsOAuth2Api": {
            "id": "google-docs-credentials",
            "name": "Google Docs"
        }
    }
}

# Node: If Has Tables (branch)
node_if_tables = {
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": ""},
            "conditions": [
                {
                    "id": "has-tables",
                    "leftValue": "={{ $json.hasTables }}",
                    "rightValue": True,
                    "operator": {"type": "boolean", "operation": "true"}
                }
            ],
            "combinator": "and"
        }
    },
    "id": "node-if-tables",
    "name": "Has Tables?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2,
    "position": [2700, 300]
}

# Node: Read Document Final (after table insertion)
node_read_doc_final = {
    "parameters": {
        "method": "GET",
        "url": "=https://docs.googleapis.com/v1/documents/{{ $('Create Google Doc').first().json.documentId }}",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "googleDocsOAuth2Api",
        "options": {}
    },
    "id": "node-read-doc-final",
    "name": "Read Document Final",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.3,
    "position": [2900, 200],
    "credentials": {
        "googleDocsOAuth2Api": {
            "id": "google-docs-credentials",
            "name": "Google Docs"
        }
    }
}

# Node: Build Table Style (Code)
BUILD_TABLE_STYLE_CODE = r"""const docId = $('Create Google Doc').first().json.documentId;
const docBody = $json.body;

if (!docBody || !docBody.content) {
  return [{ json: { docId, requests: [] } }];
}

const requests = [];

// Color palette matching the document theme
const colors = {
  navy: { red: 0.1, green: 0.15, blue: 0.3 },
  darkBlue: { red: 0.15, green: 0.25, blue: 0.45 },
  gold: { red: 0.75, green: 0.6, blue: 0.2 },
  white: { red: 1.0, green: 1.0, blue: 1.0 },
  lightGray: { red: 0.95, green: 0.96, blue: 0.97 },
  bodyText: { red: 0.15, green: 0.15, blue: 0.15 },
  borderColor: { red: 0.8, green: 0.82, blue: 0.85 }
};

const borderStyle = {
  width: { magnitude: 0.5, unit: 'PT' },
  color: { color: { rgbColor: colors.borderColor } },
  dashStyle: 'SOLID'
};

// Find all tables in the document
for (const elem of docBody.content) {
  if (elem.table) {
    const table = elem.table;
    const tableStartIndex = elem.startIndex;
    const tableEndIndex = elem.endIndex;
    const numRows = table.tableRows.length;
    const numCols = table.tableRows[0]?.tableCells?.length || 0;

    for (let r = 0; r < numRows; r++) {
      const row = table.tableRows[r];
      if (!row || !row.tableCells) continue;

      for (let c = 0; c < row.tableCells.length; c++) {
        const cell = row.tableCells[c];
        if (!cell) continue;

        const cellStart = cell.startIndex;
        const cellEnd = cell.endIndex;

        // Cell background color
        const isHeader = (r === 0);
        const isEvenRow = (r % 2 === 0);
        const bgColor = isHeader ? colors.navy : (isEvenRow ? colors.lightGray : colors.white);

        requests.push({
          updateTableCellStyle: {
            tableStartLocation: { index: tableStartIndex },
            tableCellLocation: {
              tableStartLocation: { index: tableStartIndex },
              rowIndex: r,
              columnIndex: c
            },
            tableCellStyle: {
              backgroundColor: { color: { rgbColor: bgColor } },
              paddingTop: { magnitude: 4, unit: 'PT' },
              paddingBottom: { magnitude: 4, unit: 'PT' },
              paddingLeft: { magnitude: 6, unit: 'PT' },
              paddingRight: { magnitude: 6, unit: 'PT' },
              borderTop: borderStyle,
              borderBottom: borderStyle,
              borderLeft: borderStyle,
              borderRight: borderStyle
            },
            fields: 'backgroundColor,paddingTop,paddingBottom,paddingLeft,paddingRight,borderTop,borderBottom,borderLeft,borderRight'
          }
        });

        // Text formatting for cell content
        if (cell.content) {
          for (const cellElem of cell.content) {
            if (cellElem.paragraph && cellElem.paragraph.elements) {
              for (const textEl of cellElem.paragraph.elements) {
                if (textEl.textRun && textEl.startIndex !== undefined) {
                  const textStart = textEl.startIndex;
                  const textEnd = textEl.endIndex;

                  if (textStart < textEnd) {
                    requests.push({
                      updateTextStyle: {
                        range: { startIndex: textStart, endIndex: textEnd },
                        textStyle: {
                          bold: isHeader,
                          fontSize: { magnitude: isHeader ? 10 : 9.5, unit: 'PT' },
                          foregroundColor: {
                            color: { rgbColor: isHeader ? colors.white : colors.bodyText }
                          },
                          weightedFontFamily: {
                            fontFamily: isHeader ? 'Montserrat' : 'Open Sans',
                            weight: isHeader ? 600 : 400
                          }
                        },
                        fields: 'bold,fontSize,foregroundColor,weightedFontFamily'
                      }
                    });

                    // Paragraph alignment
                    requests.push({
                      updateParagraphStyle: {
                        range: { startIndex: textStart, endIndex: textEnd },
                        paragraphStyle: {
                          alignment: 'START',
                          lineSpacing: 115,
                          spaceAbove: { magnitude: 0, unit: 'PT' },
                          spaceBelow: { magnitude: 0, unit: 'PT' }
                        },
                        fields: 'alignment,lineSpacing,spaceAbove,spaceBelow'
                      }
                    });
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}

return [{ json: { docId, requests } }];"""

node_build_table_style = {
    "parameters": {
        "jsCode": BUILD_TABLE_STYLE_CODE
    },
    "id": "node-build-table-style",
    "name": "Build Table Style",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [3100, 200]
}

# Node: Apply Table Style (HTTP batchUpdate)
node_apply_table_style = {
    "parameters": {
        "method": "POST",
        "url": "=https://docs.googleapis.com/v1/documents/{{ $json.docId }}:batchUpdate",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "googleDocsOAuth2Api",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({ requests: $json.requests }) }}",
        "options": {}
    },
    "id": "node-apply-table-style",
    "name": "Apply Table Style",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.3,
    "position": [3300, 200],
    "credentials": {
        "googleDocsOAuth2Api": {
            "id": "google-docs-credentials",
            "name": "Google Docs"
        }
    }
}

# Node: Merge after table branch (to rejoin the flow)
node_merge_table = {
    "parameters": {
        "mode": "chooseBranch",
        "output": "empty",
        "options": {}
    },
    "id": "node-merge-table",
    "name": "Merge Table Branch",
    "type": "n8n-nodes-base.merge",
    "typeVersion": 3,
    "position": [3500, 300]
}

# Add all new nodes
new_nodes = [
    node_read_doc,
    node_build_table_requests,
    node_if_tables,
    node_exec_table_requests,
    node_read_doc_final,
    node_build_table_style,
    node_apply_table_style,
    node_merge_table
]

wf['nodes'].extend(new_nodes)
print(f"  Added {len(new_nodes)} new nodes")

# ═══════════════════════════════════════════════════════════════
# 4. UPDATE CONNECTIONS
# ═══════════════════════════════════════════════════════════════

# Move Respond node further right
for node in wf['nodes']:
    if node.get('id') == 'node-respond':
        node['position'] = [3900, 300]
    elif node.get('id') == 'node-move-doc':
        node['position'] = [3700, 300]

# Remove old connection: Apply Formatting → Move to Folder
if 'Apply Formatting' in wf['connections']:
    del wf['connections']['Apply Formatting']

# Remove old connection: Move to Folder → Respond
# (keep it, it stays the same)

# Add new connections
# Apply Formatting → Read Document
wf['connections']['Apply Formatting'] = {
    "main": [[{"node": "Read Document", "type": "main", "index": 0}]]
}

# Read Document → Build Table Requests
wf['connections']['Read Document'] = {
    "main": [[{"node": "Build Table Requests", "type": "main", "index": 0}]]
}

# Build Table Requests → Has Tables?
wf['connections']['Build Table Requests'] = {
    "main": [[{"node": "Has Tables?", "type": "main", "index": 0}]]
}

# Has Tables? → true: Execute Table Requests, false: Merge Table Branch
wf['connections']['Has Tables?'] = {
    "main": [
        [{"node": "Execute Table Requests", "type": "main", "index": 0}],
        [{"node": "Merge Table Branch", "type": "main", "index": 1}]
    ]
}

# Execute Table Requests → Read Document Final
wf['connections']['Execute Table Requests'] = {
    "main": [[{"node": "Read Document Final", "type": "main", "index": 0}]]
}

# Read Document Final → Build Table Style
wf['connections']['Read Document Final'] = {
    "main": [[{"node": "Build Table Style", "type": "main", "index": 0}]]
}

# Build Table Style → Apply Table Style
wf['connections']['Build Table Style'] = {
    "main": [[{"node": "Apply Table Style", "type": "main", "index": 0}]]
}

# Apply Table Style → Merge Table Branch
wf['connections']['Apply Table Style'] = {
    "main": [[{"node": "Merge Table Branch", "type": "main", "index": 0}]]
}

# Merge Table Branch → Move to Folder
wf['connections']['Merge Table Branch'] = {
    "main": [[{"node": "Move to Folder", "type": "main", "index": 0}]]
}

# Move to Folder → Respond stays
print("  Updated connections")

# ═══════════════════════════════════════════════════════════════
# 5. WRITE MODIFIED WORKFLOW
# ═══════════════════════════════════════════════════════════════

output_path = '/home/user/n8n_seo_audit/SEO_Audit_AI_Report.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)

print(f"\n  Workflow saved to: {output_path}")
print(f"  Total nodes: {len(wf['nodes'])}")
print(f"  Total connections: {len(wf['connections'])}")
