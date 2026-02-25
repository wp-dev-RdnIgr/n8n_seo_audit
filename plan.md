# Multi-Competitor SEO Audit — Implementation Plan

## Overview
Modify the SEO audit system to support multiple competitors in a single analysis run.
All competitor results are combined into ONE Google Doc.

**Document structure**: Title page → (current 7-section structure × N competitors)

---

## Part 1: Form (pdf_audit_form.html) — AI Analysis Section

**Current**: Single text input for one spreadsheet URL.
**New**: Dynamic list of competitor URLs with "Add" / "Remove" buttons.

### Changes:
1. **Replace single input** with a dynamic competitor list container:
   - Each competitor row: `#N` label + URL input + remove button
   - "Add competitor" button below the list
   - First competitor cannot be removed
   - No limit on number of competitors

2. **Progress display** during analysis:
   - Show per-competitor progress steps (not just one spinner)
   - Each competitor: "Analyzing domain1.com..." → checkmark when done
   - Final step: "Building combined document..."

3. **Result display**:
   - Show final doc URL (one doc for all competitors)
   - Show count of competitors analyzed

### UI mockup:
```
┌─────────────────────────────────────────┐
│  AI аналіз конкурентів                  │
│                                         │
│  Конкурент 1                            │
│  [🔗 https://docs.google.com/...    ]   │
│                                         │
│  Конкурент 2                            │
│  [🔗 https://docs.google.com/...    ] ✕ │
│                                         │
│  Конкурент 3                            │
│  [🔗 https://docs.google.com/...    ] ✕ │
│                                         │
│  [+ Додати конкурента]                  │
│                                         │
│  [🤖 Запустити AI аналіз]               │
│  ⏳ ~2-4 хв на кожного конкурента       │
└─────────────────────────────────────────┘
```

---

## Part 2: Backend GAS (Код.gs) — submitAIAnalysis

**Current**: Sends single `{ url: "..." }` to webhook.
**New**: Sends `{ urls: ["url1", "url2", ...] }` array to webhook.

### Changes to `submitAIAnalysis()`:
1. Accept array of URLs instead of single URL
2. Validate each URL format
3. Send array to n8n webhook: `{ urls: [...], manager_email: "..." }`
4. Handle response with combined doc URL
5. Move doc to manager folder (same as before, but one doc)

---

## Part 3: n8n Workflow — Loop Architecture

**Current flow** (single competitor):
```
Webhook → Set Vars → Get Sheet Info → Extract Domain → Read Sheets → Prepare Data
  → 6 Agents (parallel) → Merge → Collect Sections → Final Summary
  → Prepare Document → Create Doc → Write → Format → Tables → Style → Move → Respond
```

**New flow** (multiple competitors):
```
Webhook (receives urls array)
  → Parse Input (code: create items from urls, init accumulator)
  → SplitInBatches (batch=1, sequential)
    → [loop output 0]:
        Set Variables (current URL/spreadsheetId)
        → Get Spreadsheet Info
        → Extract Domain & Folder
        → Read All Sheets
        → Prepare Data
        → 6 Agents (parallel) → Merge → Collect Sections → Final Summary
        → Store Competitor Result (code: push sections to workflow static data)
        → back to SplitInBatches
    → [done output 1]:
        Prepare Combined Document (major rewrite - builds multi-competitor doc)
        → Create Google Doc
        → Write Document Content
        → Build Format Requests
        → Apply Formatting
        → Read Document
        → Build Table Requests
        → Has Tables? → Table pipeline
        → Move to Folder
        → Respond (returns docUrl)
```

### New/Modified Nodes:

#### 3.1 NEW: "Parse Input" (Code node)
- Extracts `urls` array from webhook body
- Creates one item per URL: `[{url, index, spreadsheetId}]`
- Initializes workflow static data: `{ competitors: [] }`

#### 3.2 NEW: "SplitInBatches" node
- Batch size: 1 (process one competitor at a time)
- Output 0 → existing analysis pipeline
- Output 1 → document creation pipeline

#### 3.3 MODIFY: "Set Variables"
- Currently reads from webhook body
- Now reads from SplitInBatches output (current batch item)
- Same logic, different data source

#### 3.4 NEW: "Store Competitor Result" (Code node)
- Placed after "Final Summary Agent"
- Reads current competitor's sections (section1-6 + finalSummary)
- Reads domain name
- Pushes to workflow static data: `competitors.push({domain, sections, tables})`
- Returns item to feed back into SplitInBatches

#### 3.5 MAJOR REWRITE: "Prepare Combined Document" (replaces "Prepare Document")
- Reads ALL competitors from workflow static data
- Builds combined document:
  1. **Title page**: "SEO АУДИТ КОНКУРЕНТНОГО СЕРЕДОВИЩА" + list of domains + date
  2. **Table of Contents**: Grouped by competitor
  3. **For each competitor**:
     - Competitor separator: "━━━ КОНКУРЕНТ N: DOMAIN.COM ━━━"
     - 7 sections (same as current, numbered 01-07)
  4. **Footer**
- Generates format ranges for ALL sections across ALL competitors
- Extracts tables from ALL sections
- Outputs: docContent, formatRanges, tables

#### 3.6 MODIFY: Connection wiring
- SplitInBatches output[0] → Set Variables (start of analysis chain)
- Final Summary Agent (end of chain) → Store Competitor Result → SplitInBatches (loop back)
- SplitInBatches output[1] → Prepare Combined Document → Create Google Doc → ...

### Backward compatibility:
- If `urls` has only 1 item → works same as before (single competitor)
- Old format `{ url: "..." }` still supported (converted to array of 1)
- Document title adjusts: single = "SEO Аудит │ domain │ date", multiple = "SEO Аудит Конкурентів │ date"

---

## Implementation Order

1. **Form + GAS changes** (simpler, can test independently)
   - Modify pdf_audit_form.html
   - Modify Код.gs submitAIAnalysis

2. **n8n workflow restructuring** (complex, core logic)
   - Add Parse Input + SplitInBatches nodes
   - Add Store Competitor Result node
   - Rewrite Prepare Document → Prepare Combined Document
   - Rewire all connections
   - Test with 1 competitor (regression)
   - Test with 2-3 competitors

3. **Deploy & verify**

---

## Risk: GAS Timeout
- GAS execution limit: 6 min (consumer) / 30 min (Workspace)
- 5 competitors × 3 min = ~15 min → OK for Workspace
- 10 competitors × 3 min = ~30 min → borderline
- Mitigation: n8n responds EARLY (after creating doc with placeholder), then fills async
  - OR: Switch to async pattern with polling if needed in future
