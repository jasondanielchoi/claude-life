# Job Hunting Context

## Goal
Land a high-quality remote job. Targeted, not spray-and-pray.

## Target Profile (fill in)
- Role(s):
- Industries:
- Salary range:
- Must-haves:
- Hard nos:

## Resume Facts
- Name: Jason Daniel Choi
- Email: jasondanielchoi@gmail.com | Phone: 314.435.9101
- LinkedIn: linkedin.com/in/jason-daniel-choi
- Location: (fill in)
- Clearance: Top Secret / SCI (SSBI Dec 2010)
- Languages: English (native), Mandarin, Spanish (working)
- Current: Senior Data Scientist & Full Stack Engineer, Constituent Connection (Mar 2022–Present, remote)
- Experience: 5+ yrs data engineering, large-scale pipelines, ETL, backend dev
- Stack: Python (Django, Pandas, Dask, NumPy, scikit-learn, PyTorch), PostgreSQL, AWS (EC2/S3/Lambda/Textract), Docker, React/TypeScript, SQL, Linux
- Notable: 100M+ row pipelines, FEC/Census data systems, ballot signature validation (AWS Textract), SMS/MMS delivery at scale, built custom 128GB/32-thread local ML workstation
- Education: MS Data Analytics & Statistics + MS CS (WashU), MAcc (UW-Madison), BA Economics/Finance (WashU)

## CV & Cover Letter Source
- Path: `/Users/jasonchoi/Documents/CVS/`
- Current CV: `Wharton/Jason_Choi_CV_18FEB2026.docx`
- Note: legacy folder structure — reorganize as needed

## Job Boards to Scrape
- Remote OK, We Work Remotely, LinkedIn, Wellfound (AngelList)

## Workflow
1. `brave-search` / `puppeteer` — find and scrape listings
2. Evaluate fit against target profile
3. Draft tailored cover letter / outreach
4. Log to `applications/tracker.db` (SQLite)

## Tracking Schema
- date_found, company, role, url, status, notes, follow_up_date
