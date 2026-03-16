# n8n SEO Audit — Інструкція

## Архітектура проєкту

Система збору та аналізу SEO-даних: n8n (автоматизація) + Supabase (БД) + Google Apps Script (UI) + Browse AI (скрапінг SimilarWeb).

### Структура репозиторію
```
Comparing SimilarWeb/    — основний воркфлоу порівняння + GAS-код панелі
  gas/                   — Code.gs, Index.html, JavaScript.html, Stylesheet.html
SEO-audit/               — воркфлоу SEO-аудиту + генерація звітів
  gas/                   — Код.gs, analiz_domenu_form.html
  Tech-audit/            — технічний аудит
WS-DB/                   — staging-воркфлоу для WS-даних + SQL для Metabase
supabase/migrations/     — міграції БД (001-006)
```

## Підключення

### n8n
- URL: https://n8n.rnd.webpromo.tools
- MCP: https://n8n.rnd.webpromo.tools/mcp-server/http
- MCP Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Zjc3NjZjMS04ZTZkLTQ3OGYtYTY2Ny05MzYxOWJhMzVkYmUiLCJpc3MiOiJuOG4iLCJhdWQiOiJtY3Atc2VydmVyLWFwaSIsImp0aSI6IjJmYWMzY2JlLTRkM2UtNDY1MC05YzgwLTFhOWNhOGZjOTdlMCIsImlhdCI6MTc2ODgyNjU0N30.wEpv9lvPPq0cmccRzv1MPMJ4SM2Cmw0cMjL1dDBUlt4
- API Key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Zjc3NjZjMS04ZTZkLTQ3OGYtYTY2Ny05MzYxOWJhMzVkYmUiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzcxODY0MDI1fQ.pDWUjuqs6RF51PEKQtTHOUFJPvOF4YLFFsBWaCoL5I8
- Папка: Personal > Cloude Folder > Comparing SimilarWeb

### Supabase
- URL: https://utvoegofnctfwrjdxjvf.supabase.co
- Anon Key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV0dm9lZ29mbmN0ZndyamR4anZmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIwMzI1MjUsImV4cCI6MjA4NzYwODUyNX0.omrJJnkJLpR6eWcF4V7U4KuUhsuoeXemegL5u2UwZkk
- Publishable Key: sb_publishable_AIkq07p2eR64JWB8e2kfvg_EQ5ilj41
- Secret Key: зберігається локально (не комітити!)

## Воркфлоу (n8n)

| Воркфлоу | ID | Призначення |
|---|---|---|
| Comparing SimilarWeb - supa base | `0CBCcR9vJbKc3kdH` | Основний збір даних SimilarWeb |
| Retry Stale Tasks | `CY98aGb6C0FgfzeD` | Повторна обробка зависших задач |
| SEO Audit AI Report Generator | `BAekxapYobfgHYTt` | AI-генерація SEO-звітів |
| Monthly Email Report | `3qMKc3cKh0uLJ3v1` | Щомісячна email-розсилка |
| Comparing SimilarWeb (legacy) | `C5gcCnSahblLUIjZ` | Стара версія, не використовувати |

## Credentials (n8n)

| Сервіс | ID | Назва |
|---|---|---|
| Postgres (Supabase) | `pMaO4BlxABjfSxvT` | Postgres - supabase [ SimmilarWebCompair] |
| Telegram | `mHbM43fsaWN90avF` | I.Redin - ws tg log |
| Google Drive | `Nl36H51nJBoCaf67` | Google Drive for n8n |
| Google Sheets | `hMp9ISVYVcdpImYl` | Google Sheets account |
| Google Docs | `hb1wRTQP0sY6dAnx` | N8N_Google Docs account |
| OpenAI | `b1hLC5E1Ad7p27A9` | OpenAi - course generator |
| Browse AI | `4IkSClA1cWUZRGFP` | Browse AI 2.1 |

## Схема БД (Supabase)

```sql
clients (id, client_site, employee_email, client_status, folder_id, spreadsheet_id)
competitors (id, client_id, competitor_site)
similarweb_data (id, client_id, site, site_type, period,
    monthly_visits, unique_visitors, visit_duration, pages_per_visit, bounce_rate,
    direct, organic_search, paid_search, display_ads, social, email, ai_traffic)
task_queue (id, queue_id, client_id, client_site, sites_list,
    chunk_index, total_chunks, period, status, priority, task_id)
error_logs (id, task_id, robot_type, period, sites, status,
    error_message, resolved, retry_count)
```

## Правила роботи

1. **Не комітити секрети** — Secret Key, .env файли мають бути в .gitignore
2. **Legacy воркфлоу** `C5gcCnSahblLUIjZ` — тільки для довідки, не змінювати
3. **Міграції БД** — додавати наступний номер (зараз останній — 006)
4. **GAS-код** — зберігається в `gas/` папках відповідних модулів
5. **Бекапи воркфлоу** — зберігати перед змінами як `workflow_backup*.json`
