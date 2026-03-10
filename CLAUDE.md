# Project: n8n SEO Audit

## n8n Instance
- URL: https://n8n.rnd.webpromo.tools
- MCP Server: https://n8n.rnd.webpromo.tools/mcp-server/http
- MCP Access Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Zjc3NjZjMS04ZTZkLTQ3OGYtYTY2Ny05MzYxOWJhMzVkYmUiLCJpc3MiOiJuOG4iLCJhdWQiOiJtY3Atc2VydmVyLWFwaSIsImp0aSI6IjJmYWMzY2JlLTRkM2UtNDY1MC05YzgwLTFhOWNhOGZjOTdlMCIsImlhdCI6MTc2ODgyNjU0N30.wEpv9lvPPq0cmccRzv1MPMJ4SM2Cmw0cMjL1dDBUlt4
- API Key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Zjc3NjZjMS04ZTZkLTQ3OGYtYTY2Ny05MzYxOWJhMzVkYmUiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzcxODY0MDI1fQ.pDWUjuqs6RF51PEKQtTHOUFJPvOF4YLFFsBWaCoL5I8

## n8n Folder Structure
- Workflows are in: Personal > Cloude Folder > Comparing SimilarWeb

## Key Credentials in n8n
- Postgres (Supabase): id=pMaO4BlxABjfSxvT, name="Postgres - supabase [ SimmilarWebCompair]"
- Telegram: id=mHbM43fsaWN90avF, name="I.Redin - ws tg log"
- Google Drive OAuth2: id=Nl36H51nJBoCaf67, name="Google Drive for n8n"
- Google Sheets OAuth2: id=hMp9ISVYVcdpImYl, name="Google Sheets account"
- Google Docs OAuth2: id=hb1wRTQP0sY6dAnx, name="N8N_Google Docs account"
- OpenAI: id=b1hLC5E1Ad7p27A9, name="OpenAi - course generator"
- Browse AI: id=4IkSClA1cWUZRGFP, name="Browse AI 2.1"

## Key Workflows
- Comparing SimilarWeb - supa base: id=0CBCcR9vJbKc3kdH (main data collection)
- Retry Stale Tasks: id=CY98aGb6C0FgfzeD
- Comparing SimilarWeb: id=C5gcCnSahblLUIjZ (legacy)
- SEO Audit AI Report Generator: id=BAekxapYobfgHYTt
- Monthly Email Report - SimilarWeb: id=3qMKc3cKh0uLJ3v1 (email reports)

## Supabase Tables
- clients (id, client_site, employee_email, client_status, folder_id, spreadsheet_id)
- competitors (id, client_id, competitor_site)
- similarweb_data (id, client_id, site, site_type, period, monthly_visits, unique_visitors, visit_duration, pages_per_visit, bounce_rate, direct, organic_search, paid_search, display_ads, social, email, ai_traffic)
- task_queue (id, queue_id, client_id, client_site, sites_list, chunk_index, total_chunks, period, status, priority, task_id)
- error_logs (id, task_id, robot_type, period, sites, status, error_message, resolved, retry_count)
