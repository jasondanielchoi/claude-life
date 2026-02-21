# Job Hunting Context

## Goal
Land a high-quality remote job. Targeted, not spray-and-pray.

## Target Profile (fill in)
- Role(s):
- Industries:
- Salary range:
- Must-haves:
- Hard nos:

## Profile
- Stored in `life.db` → `profile` table (id=1) — query with `SELECT * FROM profile`
- No PII in this file; cv_path and cv_updated are in the DB row

## CV & Cover Letter Source
- Path: `~/Documents/CVS/` (local only, not in repo)
- Current CV: see `profile.cv_path` in DB

## Job Boards to Scrape
- Remote OK, We Work Remotely, LinkedIn, Wellfound (AngelList)

## Workflow
1. `brave-search` / `puppeteer` — find and scrape listings
2. Evaluate fit against target profile
3. Draft tailored cover letter / outreach
4. Log to `applications/tracker.db` (SQLite)

## Tracking Schema
- date_found, company, role, url, status, notes, follow_up_date
