# Life Ops — Jason Choi

Scope tools (venv, .nvmrc) per subdomain.

## Python Environment
- Root venv: `~/life/.venv` — ALWAYS use this for pip installs
- Never `pip install` to system Python
- Correct: `~/life/.venv/bin/pip install <pkg>`
- Correct: `~/life/.venv/bin/python3 <script>`
- Bash tool cannot persist `source activate` across calls — use full venv paths instead

## Subdomains
- `trading/` — markets
- `jobs/` — remote job hunt
- `ideas/` — business ideas
- `apps/` — building apps

## API Keys
- Never hardcode in .md files
- Google key: `~/life/.env` (gitignored, project-scoped)
- Brave Search, GitHub: `~/.claude.json` (user-scoped MCP env vars)
- Google key services: Maps, Geocoding, Places, Directions (direct); Gmail, Drive, Sheets, Calendar, Contacts (needs OAuth2)

## MCPs (user-scoped, all sessions)
- fetch, puppeteer — web scraping
- memory — cross-session persistence
- sequential-thinking — structured reasoning
- sqlite — local DB (`/Users/jasonchoi/life/data/life.db`)
- brave-search — web search
- github — code management
- gmail, gdrive, sheets, calendar, contacts — OAuth2 complete
- Token: `~/cred/google_token.json` (auto-refreshes)
- Auth helper: `~/life/google_auth.py` — `get_credentials(scopes)`

## Google Integration Library (`~/life/lib/`)
- `lib/google_factory.py` — `GoogleServiceFactory`: single credential, lazy-loads gmail/calendar/sheets/drive/people
- `lib/gmail_client.py`    — `GmailClient`: search, get_thread, send_message, create_draft, label/archive/trash
- `lib/calendar_client.py` — `CalendarClient`: get_today_events, get_upcoming_events, create_event
- `lib/sheets_client.py`   — `SheetsClient`: read/write/append ranges, create_spreadsheet, format_header_row
- `lib/drive_client.py`    — `DriveClient`: list_files, upload_file, download_file, share_with_anyone
- `lib/contacts_client.py` — `ContactsClient`: search, get_by_email, list_all
- `lib/models.py`          — Typed dataclasses: EmailMessage, EmailThread, CalendarEvent, Contact, DriveFile
- `lib/base.py`            — `BaseScript` ABC: rotating logs to ~/life/logs/, JSON stdout output

## Productivity Scripts (`~/life/scripts/`)
Run with: `~/life/.venv/bin/python3 ~/life/scripts/<script>.py [--debug]`

- `scripts/daily_digest.py`  — Today's calendar + important unread email → JSON (call at session start)
  Flags: --days-ahead N
- `scripts/email_triage.py`  — Unread Gmail threads → structured JSON for Claude to action
  Flags: --limit N, --query "gmail search string"

Logs: `~/life/logs/<scriptname>.log` (rotating, 2MB × 5 backups)
