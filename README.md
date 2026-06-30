# Visl AI — Candidate Screening Platform

An AI-powered recruitment pipeline that ingests a candidate dataset (CSV or XLSX),
evaluates resumes against a job description via Google's Gemini API, analyzes GitHub
activity, ranks candidates, emails test links to shortlisted candidates, ingests test
results, and auto-schedules interviews with real Google Calendar events and Meet links.

## Stack

- **Backend:** FastAPI, SQLAlchemy (SQLite), Google Gemini API, GitHub REST API, Google
  Calendar API
- **Frontend:** React + Vite + Tailwind CSS
- **Email:** SMTP (Gmail App Password)
- **Hosting:** Render (backend), Vercel (frontend)

## Project structure

```
visl-screening-final/
backend/
  main.py                  - FastAPI app, all endpoints
  models.py                - SQLAlchemy Candidate model (keyed by s_no)
  database.py               - DB engine/session
  services/
    resume_parser.py        - downloads + extracts text from PDF/DOCX resumes
    ai_evaluator.py          - Gemini-based JD-match scoring
    github_analyzer.py       - GitHub repo-level analysis + explainable scoring
    email_service.py         - SMTP test-link and interview emails
    calendar_service.py      - Google Calendar event + Meet link creation
  requirements.txt
  .env.example
frontend/
  src/
    App.jsx                  - pipeline dashboard (5 stages)
    api.js                    - API client
    components/
      StageCard.jsx
      CandidateTable.jsx
  package.json
  .env.example
sample_data/
  candidate_dataset.xlsx     - the dataset provided for evaluation
ARCHITECTURE.md
```

## Dataset schema

`candidate_dataset.xlsx` has two sheets:

**`Response`** - one row per candidate: `s_no, name, email, college, branch, cgpa,
best_ai_project, research_work, github, resume, test_la, test_code`. The `test_la`/
`test_code` columns here are **ignored on candidate upload** (see design notes below).

**`Test Result`** - a smaller, separate set of rows: `s_no, name, email, college, branch,
cgpa, test_la, test_code`. This is the authoritative sheet for test scores, read via the
dedicated `/upload-test-results` endpoint.

Both upload endpoints accept `.csv` or `.xlsx`. For `.xlsx`, the system looks for a sheet
named `Response` or `Test Result` respectively, falling back to the first sheet if no
match - so a plain CSV with the same column names works identically.

### Design notes

- **Candidates are matched by `s_no`, not email.** The provided dataset has every
  candidate sharing one email address; `s_no` (the dataset's own row ID) is used as the
  stable join key instead, which is also a more robust pattern for production data in
  general.
- **Only `/upload-test-results` is trusted for test scores.** Any test columns present in
  the `Response` sheet at initial candidate upload are ignored - they're treated as
  stale/placeholder values, since the assignment's own workflow models test results as a
  separate event happening after candidates are shortlisted and actually take the test.

Full reasoning for both decisions is in `ARCHITECTURE.md`.

## Prerequisites

- Python 3.10+
- Node.js 18+
- A Google Gemini API key (aistudio.google.com - free, no credit card required)
- A GitHub personal access token (optional, raises API rate limit from 60 to 5000 req/hr)
- A Gmail account with an App Password (not your normal password)
- A Google Cloud project with the Calendar API enabled and an OAuth Desktop client

## Backend setup

```
cd backend
python -m venv venv
source venv/bin/activate        (Windows: venv\Scripts\activate)
pip install -r requirements.txt
cp .env.example .env            (fill in your keys)
```

### Getting a Gemini API key

1. Go to aistudio.google.com
2. Sign in with a Google account
3. Click Get API key -> Create API key
4. Copy it into `.env` as `GEMINI_API_KEY`

No credit card is required. The free tier is rate-limited (requests per minute/day) rather
than a draining credit balance, which makes it more predictable for repeated testing than
some pay-as-you-go routers.

### Google Calendar OAuth setup (one-time, ~10 min)

1. Go to console.cloud.google.com -> create a new project.
2. Enable the Google Calendar API (APIs & Services -> Library).
3. OAuth consent screen -> External -> fill basic info -> add yourself as a Test User
   (this step is mandatory, or Google blocks the login with "Access blocked: app not
   verified").
4. Credentials -> Create Credentials -> OAuth Client ID -> Application type Desktop app.
5. Download the JSON and save it as `backend/credentials.json`.
6. On first call to `/schedule-interviews`, a browser window opens asking you to
   authorize - this generates `backend/token.pickle`, reused afterward.

### Gmail App Password (one-time, ~2 min)

Google Account -> Security -> 2-Step Verification -> App Passwords -> generate a
16-character password -> put it in `.env` as `SMTP_APP_PASSWORD`.

### Run the backend

```
uvicorn main:app --reload --port 8000
```

API docs available at http://localhost:8000/docs.

## Frontend setup

```
cd frontend
npm install
cp .env.example .env            (set VITE_API_URL to your backend URL)
npm run dev
```

Visit http://localhost:5173.

## Using the platform - end-to-end workflow

1. Upload candidates - upload `sample_data/candidate_dataset.xlsx` (reads the `Response`
   sheet automatically), or your own CSV/XLSX with the same column names.
2. Provide job description - paste a JD, click "Run AI Evaluation." Resumes are
   downloaded (Google Drive share links are auto-converted to direct-download URLs) and
   scored against the JD via Gemini; GitHub profiles are scored via the deterministic
   repo-level formula. A blended pre-test score (60% JD match, 40% GitHub) is computed.
3. Shortlist & send - set a score threshold and a test link. Candidates above the
   threshold get an automated email.
4. Upload test results - upload the same dataset again (this time it reads the `Test
   Result` sheet), or your own CSV/XLSX with `s_no, test_la, test_code` columns. Final
   score becomes 50% pre-test score + 50% test average.
5. Schedule interviews - set a final-score threshold. Qualified candidates get a real
   Google Calendar event with an auto-generated Meet link, 30 minutes apart starting the
   next day at 10:00 IST, plus an email invite.

All stages are visible in the dashboard with a live ranked candidate table (showing both
rank and the dataset's own `s_no`, since display names can repeat) and an activity log.

## API reference

| Endpoint | Method | Purpose |
|---|---|---|
| /upload-candidates | POST | Upload candidate CSV/XLSX (Response sheet) |
| /evaluate | POST | Run AI resume + GitHub evaluation against a JD |
| /candidates | GET | List all candidates, ranked by final score |
| /candidates/{id} | GET | Full detail for one candidate, including explanation text |
| /shortlist | POST | Email test links to candidates above a threshold |
| /upload-test-results | POST | Upload test score CSV/XLSX (Test Result sheet), matched by s_no |
| /schedule-interviews | POST | Create Calendar events + Meet links for qualified candidates |
| /reset | DELETE | Wipe all candidate data (dev utility) |

## Deployment

### Backend -> Render

- Root Directory: backend
- Build Command: pip install -r requirements.txt
- Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
- Environment variables: GEMINI_API_KEY, GEMINI_MODEL (optional, defaults to
  gemini-2.5-flash), GITHUB_TOKEN, SMTP_EMAIL, SMTP_APP_PASSWORD

### Calendar OAuth on a headless deploy

Google's OAuth flow needs an interactive browser, which doesn't exist on Render. The
workaround: generate `token.pickle` locally once (run the local OAuth flow, or simply hit
`/schedule-interviews` locally once and complete the browser login), then supply it to
the deployed backend as a base64-encoded environment variable rather than a file:

```
# Windows PowerShell - use absolute paths to avoid working-directory ambiguity
[Convert]::ToBase64String([IO.File]::ReadAllBytes("D:\path\to\backend\token.pickle")) | Out-File -Encoding ascii token_b64.txt
[Convert]::ToBase64String([IO.File]::ReadAllBytes("D:\path\to\backend\credentials.json")) | Out-File -Encoding ascii creds_b64.txt
```

Paste the contents of each file into Render's Environment tab as TOKEN_PICKLE_B64 and
CREDENTIALS_JSON_B64. `calendar_service.py` decodes these back into the expected files on
first use if they aren't already present locally. Delete the local `_b64.txt` files once
added to Render - they contain the same sensitive credentials in plain text.

### Frontend -> Vercel

```
npm install -g vercel
cd frontend
vercel
vercel env add VITE_API_URL production   (paste your Render backend URL)
vercel --prod
```

Note: Render's free tier spins the backend down after about 15 minutes of inactivity. The
first request after idle can take 30-60 seconds while it wakes up.

## Notes

- Resume links pointing to Google Drive share URLs are automatically converted to
  direct-download links, with a fallback for Drive's "can't scan for viruses" interstitial
  page that appears for larger files.
- All AI scoring includes a written explanation field, stored per candidate - this also
  doubles as a debugging surface, since every failure mode in the evaluation pipeline
  returns a specific, readable error into this field rather than failing silently.
- The GitHub scoring formula is fully transparent (see ARCHITECTURE.md) - no opaque LLM
  judgment is used for the GitHub score, only for JD-match scoring.
- Candidates are matched/deduplicated by s_no, not email - see "Design notes" above.
- Never commit .env, credentials.json, token.pickle, or any *_b64.txt files to version
  control. .gitignore already excludes these.
