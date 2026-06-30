# Architecture — Visl AI Candidate Screening Platform

## 1. System overview

The system is a pipeline of independent, idempotent stages, each exposed as its own API
endpoint and tracked via a `status` field on each candidate record (`uploaded` →
`evaluated` → `shortlisted` → `tested` → `interview_scheduled`). This lets a recruiter
re-run any stage safely (e.g. re-upload a corrected test-results CSV) without corrupting
candidates already past that stage.

```
CSV Upload ──► SQLite (candidates table)
                    │
                    ▼
          Job Description provided
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  Resume Parser            GitHub Analyzer
  (download + extract       (REST API, repo-level
   PDF/DOCX text)            metrics, explainable
        │                    formula)
        ▼                       │
  Claude (JD match score        │
   + explanation)               │
        └───────────┬───────────┘
                    ▼
        Combined Score = 0.6×JD + 0.4×GitHub
                    │
                    ▼
         Rank candidates, recruiter sets
              threshold → Shortlist
                    │
                    ▼
        SMTP email with test link sent
                    │
                    ▼
        Recruiter uploads test results CSV
                    │
                    ▼
   Final Score = 0.5×(pre-test score) + 0.5×(test avg)
                    │
                    ▼
        Recruiter sets interview threshold
                    │
                    ▼
     Google Calendar API creates event +
        auto-generated Meet link, 30-min
           slots, + email invite sent
```

## 2. AI evaluation approach

### 2.1 Resume vs. Job Description matching

Resume text is extracted from the candidate's resume link (PDF via `pypdf`, DOCX via
`python-docx`; Google Drive share links are normalized to direct-download URLs first).
The extracted text, along with structured profile fields (college, branch, CGPA, best AI
project, research work), is sent to Claude with the job description in a single prompt.
Claude is instructed to return strict JSON: a 0-100 match score, a list of strengths, a
list of gaps, and a short natural-language explanation. This explanation is stored
per-candidate and surfaced in the dashboard - every score is traceable to a reason, not a
black-box number.

**Why an LLM here and not embeddings/cosine similarity:** resume-to-JD matching is not
pure semantic similarity - it requires judgment about transferable skills, project
relevance despite different terminology, and academic context (e.g. a strong CGPA from a
tier-1 college on a borderline project should be weighted differently than the same
project from an unknown source). An LLM can reason about this; a vector-similarity score
cannot explain itself or apply this kind of judgment.

### 2.2 GitHub profile analysis

GitHub analysis is deliberately not LLM-based - it uses a transparent, deterministic
formula built from the GitHub REST API, evaluated at the repository level:

| Component | Max points | Logic |
|---|---|---|
| Repo count | 30 | min(non-fork repos x 5, 30) - rewards original work, ignores forks |
| Stars | 25 | min(total stars x 2, 25) - community validation signal |
| Language diversity | 20 | min(distinct languages x 5, 20) - breadth of technical exposure |
| Recent activity | 15 | flat 15 if any repo has been pushed to - recency signal |
| Profile completeness | 10 | flat 10 if bio/blog present - engagement signal |

This is intentionally explainable: a recruiter can see exactly why a candidate scored 85
vs. 40, and the breakdown is stored alongside the score (`github_details` field, exposed
via `/candidates/{id}`). The top 5 repos by stars are also fetched with name, stars,
forks, language, and description, so a recruiter can manually verify the repo-level
evaluation rather than trusting a single number.

**Why not LLM-based GitHub scoring:** repository quality assessment from code content
would require cloning and analyzing every repo's source - expensive, slow, and still
hard to make trustworthy/explainable at evaluation time within a 60-hour build window.
The chosen formula is cheap (a handful of REST calls per candidate), deterministic,
reproducible, and fully auditable.

### 2.3 Combined scoring

Two-phase weighting reflects when information becomes available:

- **Pre-test phase:** `final_score = 0.6 x jd_score + 0.4 x github_score` - resume/JD
  relevance is weighted higher because it's the most direct signal of role fit; GitHub
  acts as a secondary technical-credibility check.
- **Post-test phase:** `final_score = 0.5 x pre_test_score + 0.5 x test_avg` - once
  objective test performance (logical aptitude + coding) is available, it's blended
  equally with the qualitative pre-test signal, since a live test result is a stronger
  predictor of on-the-job performance than profile-based inference alone.

Both weightings are simple, fixed, and documented here rather than buried in code -
intentional given the bonus criterion on explainable scoring.

## 3. Automation of the recruitment workflow

Every transition in the funnel (Upload -> Provide JD -> Evaluate -> Shortlist+Email ->
Upload Tests -> Schedule Interviews) is a single API call triggered from the recruiter
dashboard, with the candidate's `status` field gating which stage they're eligible to
enter next. No manual data re-entry is required between stages - candidates carry their
identity through the entire funnel via a stable identifier (see 3.1) rather than relying
on any single column being unique by accident.

### 3.1 Candidate identity: s_no, not email

The company-provided dataset uses `s_no` (a row-level serial number) as its own implicit
primary key, and the system adopts it explicitly as the join key between the candidate
table and the test-results upload, rather than email. This is a deliberate choice over
naive email-matching: email addresses are a convenient display field but a poor identity
key in practice (typos, shared/family addresses, aliasing, re-applications under a new
email can all break uniqueness). Using an explicit ID column the source system already
provides is the more robust pattern, and costs nothing extra to implement.

### 3.2 Two-stage test-result ingestion

The provided dataset ships test scores in two places: inline on the candidate `Response`
sheet, and again in a separate `Test Result` sheet with different values for several rows.
The system treats only the dedicated `/upload-test-results` stage (sourced from `Test
Result` or an equivalent CSV) as authoritative, and ignores any test columns present at
initial candidate upload. This mirrors the assignment's own workflow, which models
"upload candidates" and "upload test results" as two separate, sequential steps separated
by the test-taking event itself - so any score visible before the candidate has actually
taken the test is necessarily stale or placeholder data, not a live result the pipeline
should trust.

## 4. GitHub analysis methodology

1. Extract username from the provided GitHub profile URL.
2. Fetch user metadata (`/users/{username}`) and up to 20 most-recently-updated repos
   (`/users/{username}/repos?sort=updated`).
3. Filter out forks to isolate original work.
4. Compute the five-component score described in section 2.2.
5. Surface the top 5 original repos by star count, with description and language, for
   recruiter spot-checking.

This is repository-level (not just profile-level) - it inspects actual repos, their
stars, forks, and languages, rather than just trusting profile bio/follower counts.

## 5. Scalability considerations

- **Stateless API layer:** FastAPI app holds no in-memory state; can be horizontally
  scaled behind a load balancer.
- **Database:** SQLite is used for the assignment's scope (single recruiter, hundreds of
  candidates). For production scale, swap to Postgres - the SQLAlchemy models require no
  changes, only the connection string in `database.py`.
- **Long-running evaluation:** `/evaluate` currently processes candidates synchronously
  in a loop. At scale (1000+ candidates), this should move to a background task queue
  (Celery/RQ/BullMQ) with per-candidate jobs, so the API responds immediately and the
  dashboard polls/streams progress instead of blocking on one HTTP request.
- **Rate limits:** GitHub's unauthenticated API is capped at 60 req/hr; the system
  supports a `GITHUB_TOKEN` env var to raise this to 5000 req/hr. For very large batches,
  GitHub API responses should be cached (e.g. Redis, keyed by username) since the same
  candidate's profile shouldn't be re-fetched on every dashboard refresh.
- **Resume downloads:** currently synchronous per-candidate; at scale this should be
  parallelized with an async HTTP client (httpx.AsyncClient + asyncio.gather) with a
  concurrency cap to avoid overwhelming source servers.
- **Email sending:** currently a direct SMTP call per candidate inside the request; at
  scale this should be queued (same job queue as evaluation) to avoid blocking the
  shortlist endpoint and to allow retry-on-failure.

## 6. Explainability (bonus)

Every score in the system is paired with a reason a human can read without re-running
the model:
- JD match score -> Claude's own `explanation` string, stored per candidate.
- GitHub score -> fully deterministic formula with a stored component-by-component
  breakdown (`score_breakdown`).
- Final score -> simple, fixed, documented arithmetic (no hidden weighting).

This was a deliberate design choice over an end-to-end "black box" LLM score: a
recruiter making hiring decisions needs to be able to defend why a candidate was ranked
where they were.
