# Visl AI — Candidate Screening Platform

An AI-powered recruitment pipeline that ingests a candidate dataset (CSV or XLSX),
evaluates resumes against a job description via an LLM, analyzes GitHub activity, ranks
candidates, emails test links to shortlisted candidates, ingests test results, and
auto-schedules interviews with real Google Calendar events + Meet links.

## Stack

- **Backend:** FastAPI, SQLAlchemy (SQLite), OpenRouter (LLM routing), GitHub REST API, Google Calendar API
- **Frontend:** React + Vite + Tailwind CSS
- **Email:** SMTP (Gmail App Password)

## Project structure

```
visl-screening/
├── backend/
│   ├── main.py                  # FastAPI app, all endpoints
│   ├── models.py                # SQLAlchemy Candidate model (keyed by s_no)
│   ├── database.py              # DB engine/session
│   ├── services/
│   │   ├── resume_parser.py     # downloads + extracts text from PDF/DOCX resumes (handles Drive links)
│   │   ├── ai_evaluator.py      # OpenRouter-based JD-match scoring
│   │   ├── github_analyzer.py   # GitHub repo-level analysis + explainable scoring
│   │   ├── email_service.py     # SMTP test-link & interview emails
│   │   └── calendar_service.py  # Google Calendar event + Meet link creation
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # pipeline dashboard (5 stages)
│   │   ├── api.js               # API client
│   │   └── components/
│   │       ├── StageCard.jsx
│   │       └── CandidateTable.jsx
│   ├── package.json
│   └── .env.example
├── sample_data/
│   └── candidate_dataset.xlsx   # the real dataset provided by the company
└── ARCHITECTURE.md
```

## Dataset schema (as provided by the company)

The `candidate_dataset.xlsx` file has two sheets:

**`Response`** — one row per candidate, columns: `s_no, name, email, college, branch, cgpa,
best_ai_project, research_work, github, resume, test_la, test_code`. Note: the
`test_la`/`test_code` columns present on this sheet are **ignored on candidate upload** —
see "Design decision" below.

**`Test Result`** — a separate, smaller set of rows: `s_no, name, email, college, branch,
cgpa, test_la, test_code`. This is the sheet the system treats as authoritative for test
scores, uploaded via the dedicated `/upload-test-results` stage.

The system accepts both `.csv` and `.xlsx` for both upload endpoints. For `.xlsx` files,
it specifically looks for a sheet named `Response` (falling back to the first sheet) on
candidate upload, and a sheet named `Test Result` (falling back to the first sheet) on
test-result upload — so you can also feed it plain CSVs with the same column names if your
own data comes that way.

### Design decision: candidates are matched by `s_no`, not email

In the provided dataset, all 10 candidates share the same email address (clearly seeded
test data using `+` aliasing). Rather than build the system fragile to that quirk, the
matching key for joining test results back to candidates is `s_no` (the dataset's own row
ID) — robust whether or not email addresses are unique, which is also safer for real
production data where duplicate/shared emails are a known edge case (typos, shared family
addresses, re-applications).

### Design decision: `Response` sheet test scores are ignored on candidate upload

The assignment's workflow treats "upload candidate dataset" and "upload test results" as
two distinct pipeline stages (steps 1 and 8 of the spec) — implying test results arrive
*after* candidates take the test post-shortlisting, as a separate event. Any `test_la`/
`test_code` values sitting in the `Response` sheet at initial upload are therefore treated
as stale/placeholder data, not live results, and are not read. Only the dedicated
`/upload-test-results` endpoint (reading the `Test Result` sheet, or any CSV with the same
column names) feeds the scoring pipeline. This also resolves the fact that the two sheets
in the real dataset have genuinely different `test_code` values for several candidates —
the system has one unambiguous source of truth.

## Prerequisites

- Python 3.10+
- Node.js 18+
- An OpenRouter API key (openrouter.ai/keys)
- A GitHub personal access token (optional but recommended — raises API rate limit from 60 to 5000 req/hr)
- A Gmail account with an **App Password** (not your normal password)
- A Google Cloud project with the Calendar API enabled and an OAuth Desktop client

## Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in your keys
```

### Google Calendar OAuth setup (one-time, ~10 min)

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a new project.
2. Enable the **Google Calendar API** (APIs & Services → Library).
3. OAuth consent screen → External → fill basic info → add yourself as a Test User.
4. Credentials → Create Credentials → OAuth Client ID → Application type **Desktop app**.
5. Download the JSON and save it as `backend/credentials.json`.
6. On first call to `/schedule-interviews`, a browser window opens asking you to authorize — this generates `backend/token.pickle`, reused afterward. On a headless server, run this flow once locally and upload the generated `token.pickle` alongside your deployment.

### Gmail App Password (one-time, ~2 min)

Google Account → Security → 2-Step Verification → App Passwords → generate a 16-character
password → put it in `.env` as `SMTP_APP_PASSWORD`.

### Run the backend

```bash
uvicorn main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`.

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env            # set VITE_API_URL to your backend URL
npm run dev
```

Visit `http://localhost:5173`.

## Using the platform — end-to-end workflow

1. **Upload candidates** — upload `sample_data/candidate_dataset.xlsx` (reads the `Response` sheet automatically), or your own CSV/XLSX with the same column names.
2. **Provide job description** — paste a JD, click "Run AI Evaluation". This downloads each resume (Google Drive share links are auto-converted to direct-download URLs), scores it against the JD via OpenRouter, and scores each GitHub profile via the repo-level analyzer. A blended pre-test score (60% JD match, 40% GitHub) is computed. Candidates with no GitHub link or no research work are handled gracefully (scored 0 / left blank, not crashed on).
3. **Shortlist & send** — set a score threshold and a test link. Candidates above the threshold get an automated email.
4. **Upload test results** — upload the same `candidate_dataset.xlsx` again (this time it reads the `Test Result` sheet), or your own CSV/XLSX with `s_no, test_la, test_code` columns. Matched by `s_no`. Final score becomes 50% pre-test score + 50% test average.
5. **Schedule interviews** — set a final-score threshold. Qualified candidates get a real Google Calendar event with an auto-generated Meet link, 30 minutes apart starting the next day at 10:00 IST, plus an email invite.

All stages are visible in the dashboard with a live ranked candidate table (showing both
rank and the dataset's own `s_no`, since this data has duplicate display names) and an
activity log.

## API reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/upload-candidates` | POST | Upload candidate CSV/XLSX (`Response` sheet) |
| `/evaluate` | POST | Run AI resume + GitHub evaluation against a JD |
| `/candidates` | GET | List all candidates, ranked by final score |
| `/candidates/{id}` | GET | Full detail for one candidate |
| `/shortlist` | POST | Email test links to candidates above a threshold |
| `/upload-test-results` | POST | Upload test score CSV/XLSX (`Test Result` sheet), matched by `s_no` |
| `/schedule-interviews` | POST | Create Calendar events + Meet links for qualified candidates |
| `/reset` | DELETE | Wipe all candidate data (dev utility) |

## Deployment

**Backend → Render / Railway / Fly.io:**
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Set env vars: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (optional), `GITHUB_TOKEN`, `SMTP_EMAIL`, `SMTP_APP_PASSWORD`
- Upload `credentials.json` and a pre-authorized `token.pickle` as part of the deploy (Calendar OAuth can't complete interactively on a headless server).

**Frontend → Vercel / Netlify:**
- Build command: `npm run build`, output dir: `dist`
- Set `VITE_API_URL` to your deployed backend URL.

## Notes

- Resume links pointing to Google Drive share URLs are automatically converted to direct-download links, with a fallback for Drive's "can't scan for viruses" interstitial page on larger files.
- All AI scoring includes a written explanation field, stored per candidate, for explainability.
- The GitHub scoring formula is fully transparent (see `ARCHITECTURE.md`) — no opaque LLM judgment is used for the GitHub score, only for JD-match scoring.
- Candidates are matched/deduplicated by `s_no`, not email — see "Design decision" above.
