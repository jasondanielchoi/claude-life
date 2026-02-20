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
- Google key services: Maps, Geocoding, Places, Directions (direct); all others need OAuth2

## MCPs (user-scoped, all sessions)
- fetch, puppeteer — web scraping
- memory — cross-session persistence
- sequential-thinking — structured reasoning
- sqlite — local DB (`/Users/jasonchoi/life/data/life.db`)
- brave-search — web search
- github — code management
- Token: `~/cred/google_token.json` (auto-refreshes, 11 scopes)
- Auth helper: `~/life/google_auth.py` — `get_credentials(scopes)`
- Re-auth script: `~/life/reauth.py` — use when scopes change

## Google Integration Library (`~/life/lib/`)

### Factory
- `lib/google_factory.py` — `GoogleServiceFactory`: single credential, lazy-loads all 11 services

### Original clients
- `lib/gmail_client.py`    — `GmailClient`: search, get_thread, send_message, create_draft, label/archive/trash
- `lib/calendar_client.py` — `CalendarClient`: get_today_events, get_upcoming_events, create_event
- `lib/sheets_client.py`   — `SheetsClient`: read/write/append ranges, create_spreadsheet, format_header_row
- `lib/drive_client.py`    — `DriveClient`: list_files, upload_file, download_file, share_with_anyone
- `lib/contacts_client.py` — `ContactsClient`: search, get_by_email, list_all

### New clients
- `lib/docs_client.py`         — `DocsClient`: get_document, create_document, append_text, replace_text, batch_update
- `lib/slides_client.py`       — `SlidesClient`: get_presentation, create_presentation, get_text_content, add_slide
- `lib/tasks_client.py`        — `TasksClient`: list_task_lists, get_tasks, create_task, complete_task, update_task
- `lib/keep_client.py`         — `KeepClient`: list_notes, create_note, get_note, delete_note ⚠️ Workspace only
- `lib/meet_client.py`         — `MeetClient`: create_space, get_space, end_active_conference
- `lib/drive_labels_client.py` — `DriveLabelsClient`: list_labels, get_label, apply_label, remove_label, get_file_labels

### Models
- `lib/models.py` — All typed dataclasses:
  Original: EmailMessage, EmailThread, CalendarEvent, Contact, DriveFile
  New: GoogleDoc, Presentation, Slide, Task, TaskList, KeepNote, MeetingSpace, DriveLabel, LabelField
- `lib/base.py`   — `BaseScript` ABC: rotating logs to ~/life/logs/, JSON stdout output

## Productivity Scripts (`~/life/scripts/`)
Run with: `~/life/.venv/bin/python3 ~/life/scripts/<script>.py [--debug]`

- `scripts/daily_digest.py`  — Today's calendar + important unread email → JSON (call at session start)
  Flags: --days-ahead N
- `scripts/email_triage.py`  — Unread Gmail threads → structured JSON for Claude to action
  Flags: --limit N, --query "gmail search string"

Logs: `~/life/logs/<scriptname>.log` (rotating, 2MB × 5 backups)
