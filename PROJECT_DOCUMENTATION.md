# SEO Audit Automation Platform - Documentation

## 1. Overview

Automated platform for comprehensive SEO analysis. Built on **n8n** (workflow automation), **Google Apps Script** (frontend + backend glue), and external APIs (Ahrefs, SimilarWeb, Serpstat, Google Ads, OpenAI). The system collects SEO data for domains, generates AI-powered reports, parses PDF audits, and performs keyword research through Google Keyword Planner.

---

## 2. Storage & Repositories

| Resource | URL | Description |
|----------|-----|-------------|
| **Google Apps Script** | https://script.google.com/home/projects/1UM5kbeqZwQUuv4fe-cz61xjaLxYSNMH7DkFW7ez8YmIn3MCNlQNBmcCL/edit?pli=1 | Frontend (HTML forms) + Backend (webhook proxies). Deployed as Web App |
| **GitHub** | https://github.com/wp-dev-RdnIgr/n8n_seo_audit | Version control for GAS code + n8n workflow JSONs |
| **Google Drive** | https://drive.google.com/drive/u/0/folders/1A3Ak929G1c4XmZpPtI2FP4glrFE2-Bx2 | Root folder for all generated reports. Sub-folders per manager/project |
| **Web Interface** | https://sites.google.com/web-promo.com.ua/seo-audit/%D0%B3%D0%BE%D0%BB%D0%BE%D0%B2%D0%BD%D0%B0/%D1%82%D0%B5%D1%85-%D0%B0%D0%BD%D0%B0%D0%BB%D0%B8%D0%B7?authuser=0 | Google Sites page embedding GAS forms via iframe |
| **Browse AI** | https://dashboard.browse.ai/workspaces/web-promo-com-ua/robots | Bot parsers for SimilarWeb scraping |
| **n8n Instance** | https://n8n.rnd.webpromo.tools | Self-hosted n8n with all workflows |
| **n8n MCP Server** | https://n8n.rnd.webpromo.tools/mcp-server/http | MCP protocol endpoint for AI agent access |

---

## 3. Architecture

```
[Google Sites page]
    |
    |-- iframe --> [GAS Web App (?page=...)]
                       |
                       |-- google.script.run --> [Kod.gs backend functions]
                                                     |
                                                     |-- UrlFetchApp.fetch() --> [n8n webhooks]
                                                                                      |
                                                                                      |-- [n8n workflows]
                                                                                           |-- Ahrefs API (MCP)
                                                                                           |-- Google Ads API
                                                                                           |-- Serpstat API
                                                                                           |-- Browse AI
                                                                                           |-- OpenAI API
                                                                                           |-- Google Drive/Sheets/Docs API
                                                                                           |-- PageSpeed Insights API
```

---

## 4. GAS Frontend - Pages & Routing

Routing is done via URL parameter `?page=...` in `doGet(e)` function (`Kod.gs`, line 5).

| Page param | HTML File | Title | Description |
|------------|-----------|-------|-------------|
| `audit` (default) | `form.html` | Analiz domenu | Domain analysis - inputs domain, gets full SEO audit spreadsheet + AI report button |
| `master` | `analiz_domenu_form.html` | Analiz domenu - Master | Orchestrator form with 5 toggle-sections: client, competitors, semantic, metrics, PageSpeed |
| `gkp` | `gkp_form.html` | Semantichne yadro (GKP) | Legacy GKP form with manual seed keywords entry (tags) |
| `gkp_ideas` | `gkp_ideas.html` | GKP: Generaciya idey | Stage 1 - generate keyword ideas from spreadsheet with seed phrases |
| `gkp_metrics` | `gkp_metrics.html` | GKP: Metriki | Stage 2 - get search volume metrics for keywords from spreadsheet |
| `pagespeed` | `pagespeed_form.html` | PageSpeed Test | Mass PageSpeed testing from spreadsheet URLs |
| `pdf_audit` | `pdf_audit_form.html` | SEO AI Instrumenti | Two sections: AI domain analysis + PDF audit parser |

---

## 5. GAS Backend Functions (Kod.gs)

### 5.1 `submitAudit(domain)`
- **Called from:** `form.html` (Analiz domenu page)
- **Webhook:** `POST https://n8n.rnd.webpromo.tools/webhook/seo-organic-traffic-v74`
- **Payload:** `{ domain, country: "ua", top_pages_limit: 50 }`
- **Response:** `{ success, spreadsheetUrl, message }`
- **What it does:** Triggers full domain SEO audit (Ahrefs + SimilarWeb + Serpstat). Returns link to Google Sheet.

### 5.2 `submitAIAnalysis(spreadsheetUrl)`
- **Called from:** `form.html` (AI section) and `pdf_audit_form.html` (AI domain analysis card)
- **Webhook:** `POST https://n8n.rnd.webpromo.tools/webhook-test/seo-audit-ai-report`
- **Payload:** `{ url: spreadsheetUrl }`
- **Response:** `{ success, docUrl, domain, message }`
- **What it does:** Sends spreadsheet to AI for analysis. GPT-4o reads all 6 sheets, generates formatted Google Doc report.

### 5.3 `submitAnalizDomenu(formData)`
- **Called from:** `analiz_domenu_form.html` (Master page)
- **Webhook:** `POST https://n8n.rnd.webpromo.tools/webhook/analiz-domenu`
- **Payload:** Complex object with manager_email + optional blocks (client_domain, competitors[], semantic_expansion, metrics_collection, pagespeed)
- **Response:** `{ success, folderUrl, details, message }`
- **What it does:** Master orchestrator. Creates Google Drive folder structure, runs selected analysis blocks sequentially.

### 5.4 `submitGKP(formData)` (legacy)
- **Called from:** `gkp_form.html`
- **Webhook:** `POST https://n8n.rnd.webpromo.tools/webhook/gkp-ideas`
- **Payload:** `{ doc_name, language, geo_target, seed_keywords, url_mapping, limit }`
- **Response:** `{ success, spreadsheetUrl, totalKeywords, totalClusters, message }`

### 5.5 `submitGKPIdeas(formData)`
- **Called from:** `gkp_ideas.html`
- **Webhook:** `POST https://n8n.rnd.webpromo.tools/webhook/gkp-ideas`
- **Payload:** `{ doc_name, language, geo_target, source_spreadsheet_id }`
- **Response:** `{ success, spreadsheetUrl, totalKeywords, totalBatches, message }`

### 5.6 `submitGKPMetrics(formData)`
- **Called from:** `gkp_metrics.html`
- **Webhook:** `POST https://n8n.rnd.webpromo.tools/webhook/gkp-metrics`
- **Payload:** `{ doc_name, language, geo_target, source_spreadsheet_id }`
- **Response:** `{ success, spreadsheetUrl, totalKeywords, keywordsWithData, keywordsNoData, message }`

### 5.7 `submitPageSpeedTest(formData)`
- **Called from:** `pagespeed_form.html`
- **Webhook:** `POST https://n8n.rnd.webpromo.tools/webhook/pagespeed-test`
- **Payload:** `{ spreadsheetId, testMobile, testDesktop, batchSize: 5, delaySeconds: 5 }`
- **Response:** `{ success, spreadsheetUrl, totalUrls, processingTime, message }`

### 5.8 `submitPdfAuditParse(formData)`
- **Called from:** `pdf_audit_form.html` (PDF parser card)
- **Webhook:** `POST https://n8n.rnd.webpromo.tools/webhook-test/parse-pdf-audit`
- **Payload:** `{ pdfUrl }`
- **Response:** `{ success, spreadsheetUrl, totalSheets, processingTime, message }`

---

## 6. n8n Workflows

### 6.1 SEO Domain Audit ("Sheet 8 - Traffic Pages Nodes")

**File:** `Sheet 8 - Traffic Pages Nodes (1).json`

**Webhooks:**
| Path | Method | Purpose |
|------|--------|---------|
| `seo-organic-traffic-v74` | POST | Main entry point - starts audit |
| `browse-ai-callback-v74` | POST | Callback from Browse AI when scraping completes |
| `seo-audit-full-v74` | POST | Internal trigger for full Ahrefs + Serpstat data |

**Flow:**
1. Receives domain -> creates Google Sheet -> moves to Drive folder
2. Triggers Browse AI to scrape SimilarWeb (traffic, channels, devices, social)
3. Responds immediately with spreadsheet URL (async processing)
4. Browse AI callback writes behavioral data to Sheet 1
5. Triggers Full Audit internally
6. Parallel Ahrefs API calls (via MCP): traffic, backlinks, DR, refdomains, anchors, top pages
7. Serpstat API calls: keywords with positions (up to 5000, paginated)
8. Generates 8 sheets:

| Sheet # | Name | Data Source | Content |
|---------|------|-------------|---------|
| 1 | Organichniy_trafik | Ahrefs + SimilarWeb | Traffic overview, history, geo distribution, channels |
| 2 | (embedded in Sheet 1) | SimilarWeb/Browse AI | Branded vs non-branded traffic, engagement metrics |
| 3 | Posilalniy_profil | Ahrefs | DR history, refdomains, anchor text distribution |
| 4 | Vsi_beklinki | Ahrefs | All backlinks (top 100 by DR) |
| 5 | Top_storinki_za_posilannyami | Ahrefs | Top pages by referring domains |
| 6 | Povedinkovi_metriki | SimilarWeb/Browse AI | Social traffic, referrers, publishers |
| 7 | Klyuchovi_frazi | Serpstat | Up to 5000 keywords with volumes, positions, intent |
| 8 | Trafikogeneruyuchi_storinki | Serpstat (aggregated) | Pages grouped by traffic with top keyword |

**External APIs:**
- Ahrefs (MCP protocol) - domain metrics, backlinks, anchors, DR
- SimilarWeb (via Browse AI scraping) - behavioral metrics
- Serpstat API (`api.serpstat.com/v4`) - keywords
- Cloudinary - SVG chart hosting
- Google Drive/Sheets API - file management

**Input:**
```json
{
  "domain": "example.com (required)",
  "country": "ua (default)",
  "top_pages_limit": 50,
  "date_from": "auto: 1 year ago",
  "date_to": "auto: yesterday"
}
```

---

### 6.2 Master Orchestrator ("Analiz Domenu Master")

**File:** `Analiz_Domenu_Master.json`
**Webhook:** `POST /webhook/analiz-domenu`

**Flow:**
1. Receives manager email + optional analysis blocks
2. Searches/creates manager's personal folder on Google Drive (parent: `1A3Ak929G1c4XmZpPtI2FP4glrFE2-Bx2`)
3. Creates project subfolder "{domain} - {date}"
4. Sequentially runs enabled blocks:
   - Client domain audit (calls `seo-organic-traffic-v74`)
   - Competitor audits (loops with 5s delay, calls `seo-organic-traffic-v74` per competitor)
   - Semantic expansion (calls `gkp-ideas`)
   - Metrics collection (calls `gkp-metrics`)
   - PageSpeed test (calls `pagespeed-test`)
5. Moves all generated files to project folder
6. Returns folder URL + status of each block

**Input:**
```json
{
  "manager_email": "required - used for folder name",
  "client_domain": "optional",
  "competitors": ["array of domains"],
  "semantic_expansion": { "spreadsheet_url", "language", "geo_target" },
  "metrics_collection": { "spreadsheet_url", "language", "geo_target" },
  "pagespeed": { "spreadsheet_url", "test_mobile", "test_desktop" }
}
```

---

### 6.3 AI Report Generator ("SEO Audit AI Report Generator")

**File:** `SEO_Audit_AI_Report.json`
**Webhook:** `POST /webhook/seo-audit-ai-report` (currently using `webhook-test`)

**Flow:**
1. Receives spreadsheet URL/ID
2. Reads all 6 data sheets via Google Sheets API batchGet
3. Runs **6 parallel GPT-4o agents** - each analyzes one sheet:
   - Agent 1: Organic traffic analysis
   - Agent 2: Link profile analysis
   - Agent 3: Top pages by links
   - Agent 4: Behavioral metrics
   - Agent 5: Keywords analysis
   - Agent 6: Traffic-generating pages
4. Merges all 6 agent outputs
5. Runs **Summary Agent** - creates executive summary from all sections
6. Creates Google Doc with:
   - Title page (SEO AUDIT, domain, date)
   - Table of Contents
   - 7 sections with professional formatting (Montserrat/Open Sans fonts, navy/gold colors)
7. Moves document to source spreadsheet's folder

**Output:** Google Doc URL with formatted AI report

---

### 6.4 PDF Audit Parser

**File:** `PDF_Audit_Parser.json`
**Webhook:** `POST /webhook/parse-pdf-audit` (currently using `webhook-test`)

**Flow:**
1. Receives Google Drive PDF URL
2. Downloads PDF from Google Drive
3. Uploads PDF to OpenAI Files API
4. Sends to GPT-4o with structured extraction prompt (temperature: 0.1)
5. Extracts 15 sections: General Info, Summary, Content Types, URL Structure, Server Codes, Indexability, Meta Robots, Canonical, URL Depth, Loading Speed, Protocols, SEO Elements, Content Metrics, Errors, Scan Settings
6. Creates new Google Sheet with formatted data
7. Applies formatting: section headers (dark blue), sub-headers (light blue), table headers (gray), grid lines
8. Deletes temporary file from OpenAI
9. Returns spreadsheet URL

**Input:** `{ "pdfUrl": "Google Drive URL" }`
**Output:** `{ "spreadsheetUrl", "totalRows", "processingTime" }`

---

### 6.5 GKP Universal System

**File:** `GKP_Universal_System.json`

**Webhooks:**
| Path | Purpose |
|------|---------|
| `gkp-ideas` | Stage 1 - generate keyword ideas from seeds |
| `gkp-metrics` | Stage 2 - get search volume for keywords |

**Stage 1 (Ideas):**
1. Reads seed phrases from Google Sheet (column A) or request body
2. Splits into batches of 10
3. Calls Google Ads API `generateKeywordIdeas` with pagination (1000/page)
4. Deduplicates, sorts by search volume
5. Writes to new Google Sheet: [Keyword, Avg Monthly Searches, Competition, Competition Index, Source Seed]

**Stage 2 (Metrics):**
1. Reads keywords from Google Sheet or body (up to 100,000)
2. Splits into batches of 10,000
3. Calls Google Ads API `generateKeywordHistoricalMetrics`
4. Writes to new Google Sheet: [Keyword, Avg Monthly Searches, Competition, Competition Index, Monthly Volumes]

**Google Ads credentials:**
- Customer ID: `3460470607`
- Login Customer ID: `3993420980`
- Developer Token: `9KarAB-iwnq1oTfRx4T55w`

---

### 6.6 PageSpeed Test

**File:** `PageSpeed_Test.json`
**Webhook:** `POST /webhook/pagespeed-test`

**Flow:**
1. Reads URLs from Google Sheet (column A)
2. Creates new sheet with 4 tabs: Mobile Results, Desktop Results, Comparison, Recommendations
3. Tests each URL via Google PageSpeed Insights API v5 (batches of 5, 5s delay)
4. Extracts: Performance, Accessibility, Best Practices, SEO, FCP, LCP, TBT, CLS, Speed Index, TTI
5. Runs GPT-4o-mini for AI commentary on each tab
6. Writes results with formatting

**PageSpeed API Key:** `AIzaSyANhdoZFJJj6aa5d_GQIokvgm5VExL_2ys`

---

### 6.7 Link Profile Audit ("Zovnishnya skladova")

**File:** `Zovnishnya_skladova.json`
**Webhook:** `POST /webhook/link-profile-audit`

**Flow:**
1. Creates folder on Google Drive (parent: `1VAwG8CkWIkhY-LRwzHqEaiHmsB0gmDCU`)
2. Creates Google Sheet with 4 tabs
3. Parallel Ahrefs API calls (MCP): DR, backlink stats, anchors (top 50), top pages (100), all backlinks (up to 5000)
4. Writes and formats 4 sheets:
   - Link Profile (DR, rank, backlinks stats)
   - Anchor List (top 50 anchors with %)
   - Top Pages (100 pages by referring domains)
   - All Backlinks (up to 5000, sorted by traffic)

**Ahrefs Bearer Token:** `3Y8C09Rxdir7dllK`

---

### 6.8 To GKP (Test Workflow)

**File:** `To GKP.json`
**Trigger:** Manual only (no webhook)
**Purpose:** Test workflow for Google Ads API. Hardcoded seed "krosivki", calls `generateKeywordIdeas`.

---

## 7. Webhook Endpoints Summary

| Endpoint Path | Method | Workflow | GAS Function |
|---------------|--------|----------|--------------|
| `/webhook/seo-organic-traffic-v74` | POST | Sheet 8 - Traffic Pages | `submitAudit()` |
| `/webhook/browse-ai-callback-v74` | POST | Sheet 8 - Traffic Pages | (internal callback) |
| `/webhook/seo-audit-full-v74` | POST | Sheet 8 - Traffic Pages | (internal trigger) |
| `/webhook/analiz-domenu` | POST | Analiz_Domenu_Master | `submitAnalizDomenu()` |
| `/webhook-test/seo-audit-ai-report` | POST | SEO_Audit_AI_Report | `submitAIAnalysis()` |
| `/webhook-test/parse-pdf-audit` | POST | PDF_Audit_Parser | `submitPdfAuditParse()` |
| `/webhook/gkp-ideas` | POST | GKP_Universal_System | `submitGKP()`, `submitGKPIdeas()` |
| `/webhook/gkp-metrics` | POST | GKP_Universal_System | `submitGKPMetrics()` |
| `/webhook/pagespeed-test` | POST | PageSpeed_Test | `submitPageSpeedTest()` |
| `/webhook/link-profile-audit` | POST | Zovnishnya_skladova | (no GAS form) |

**Note:** `/webhook-test/` endpoints are n8n test-mode webhooks (active only when workflow is open in editor). `/webhook/` endpoints are production webhooks (active when workflow is activated).

---

## 8. External API Credentials

| Service | Auth Type | Key Details |
|---------|-----------|-------------|
| **Ahrefs** | Bearer Token (MCP) | Token: `3Y8C09Rxdir7dllK` |
| **Google Ads** | OAuth2 + Developer Token | Customer: `3460470607`, Login: `3993420980`, Token: `9KarAB-iwnq1oTfRx4T55w` |
| **Serpstat** | HTTP Query Auth | via n8n credential store |
| **OpenAI** | API Key | via n8n credential store, models: `gpt-4o` (reports), `gpt-4o-mini` (PageSpeed) |
| **Google Drive/Sheets/Docs** | OAuth2 | via n8n credential store |
| **PageSpeed Insights** | API Key | `AIzaSyANhdoZFJJj6aa5d_GQIokvgm5VExL_2ys` |
| **Browse AI** | HTTP Header Auth | via n8n credential store |
| **Cloudinary** | API credentials | for SVG chart uploads |

---

## 9. Google Drive Folder Structure

```
Root: SEO - audyt (1A3Ak929G1c4XmZpPtI2FP4glrFE2-Bx2)
|
|-- [manager@email.com]/
|   |-- [domain - 2026-02-16]/
|       |-- SEO Audit - domain - date.xlsx (8 sheets)
|       |-- GKP Ideas - date.xlsx
|       |-- GKP Metrics - date.xlsx
|       |-- PageSpeed Report - date.xlsx
|       |-- SEO Audit AI Report - domain.gdoc
|
|-- Link Profile folder (parent: 1VAwG8CkWIkhY-LRwzHqEaiHmsB0gmDCU)
    |-- [domain - date]/
        |-- Link Profile Report.xlsx (4 sheets)
```

---

## 10. File Structure (Git)

```
n8n_seo_audit/
|-- .mcp.json                          # MCP server config for n8n
|-- gas/
|   |-- Kod.gs                         # Backend: routing + webhook proxy functions
|   |-- form.html                      # Page: "Analiz domenu" (domain + AI report)
|   |-- analiz_domenu_form.html        # Page: "Master" orchestrator (5 blocks)
|   |-- gkp_form.html                  # Page: GKP legacy (manual seeds input)
|   |-- gkp_ideas.html                 # Page: GKP Stage 1 (ideas from sheet)
|   |-- gkp_metrics.html               # Page: GKP Stage 2 (metrics from sheet)
|   |-- pagespeed_form.html            # Page: PageSpeed test
|   |-- pdf_audit_form.html            # Page: AI analysis + PDF parser (2 cards)
|
|-- Analiz_Domenu_Master.json          # n8n: Master orchestrator workflow
|-- SEO_Audit_AI_Report.json           # n8n: AI report generator (GPT-4o)
|-- PDF_Audit_Parser.json              # n8n: PDF to spreadsheet parser
|-- GKP_Universal_System.json          # n8n: Google Keyword Planner (ideas + metrics)
|-- PageSpeed_Test.json                # n8n: PageSpeed Insights test
|-- Sheet 8 - Traffic Pages Nodes (1).json  # n8n: Main SEO audit (Ahrefs + SimilarWeb + Serpstat)
|-- Zovnishnya_skladova.json           # n8n: Link profile audit (Ahrefs)
|-- To GKP.json                        # n8n: Test workflow (manual GKP call)
```

---

## 11. Deployment Notes

### GAS Deployment
1. Code lives in GAS editor (link in Section 2)
2. Git repo mirrors GAS files for version control
3. To deploy: copy files from `gas/` folder to GAS editor -> Deploy as Web App
4. Web App URL is embedded as iframe in Google Sites page

### n8n Workflow Deployment
1. JSON files in repo are exports of n8n workflows
2. To deploy: import JSON into n8n instance at `n8n.rnd.webpromo.tools`
3. After import: configure credentials, activate workflow
4. **Important:** `webhook-test` URLs only work when workflow is open in n8n editor. For production use, activate workflow and use `webhook` URLs.

### Current webhook-test note
Two functions (`submitAIAnalysis`, `submitPdfAuditParse`) currently point to `webhook-test` URLs. This means they will only work when the corresponding workflows are open in n8n editor. For production: change to `webhook` and activate the workflows.
