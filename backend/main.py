import io
import datetime
from dotenv import load_dotenv

load_dotenv()

import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine, SessionLocal
from models import Candidate
from services.resume_parser import download_and_extract
from services.ai_evaluator import evaluate_resume
from services.github_analyzer import analyze_github
from services.email_service import send_test_link, send_interview_invite
from services.calendar_service import schedule_interview

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Visl AI Candidate Screening Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Source dataset uses lowercase/underscore column names: s_no, name, email, college,
# branch, cgpa, best_ai_project, research_work, github, resume, [test_la, test_code]
REQUIRED_CANDIDATE_COLUMNS = [
    "s_no", "name", "email", "college", "branch", "cgpa",
    "best_ai_project", "github", "resume"
]


def _read_table(file: UploadFile, contents: bytes) -> pd.DataFrame:
    """Read CSV or XLSX (first sheet, or a sheet literally named 'Response' if present)."""
    filename = (file.filename or "").lower()
    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        xl = pd.ExcelFile(io.BytesIO(contents))
        sheet = "Response" if "Response" in xl.sheet_names else xl.sheet_names[0]
        return pd.read_excel(xl, sheet_name=sheet)
    return pd.read_csv(io.BytesIO(contents))


def _read_test_results_table(file: UploadFile, contents: bytes) -> pd.DataFrame:
    """Read CSV or XLSX for test results. Prefers a sheet named 'Test Result' if present."""
    filename = (file.filename or "").lower()
    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        xl = pd.ExcelFile(io.BytesIO(contents))
        sheet = "Test Result" if "Test Result" in xl.sheet_names else xl.sheet_names[0]
        return pd.read_excel(xl, sheet_name=sheet)
    return pd.read_csv(io.BytesIO(contents))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def root():
    return {"status": "ok", "service": "Visl AI Candidate Screening Platform"}


@app.post("/upload-candidates")
async def upload_candidates(file: UploadFile = File(...)):
    """Upload candidate dataset (.csv or .xlsx). Required columns:
    s_no, name, email, college, branch, cgpa, best_ai_project, github, resume.
    Optional: research_work.
    Note: any test_la/test_code columns present here are intentionally IGNORED —
    test scores are only accepted via the dedicated /upload-test-results stage."""
    try:
        contents = await file.read()
        df = _read_table(file, contents)
    except Exception as e:
        raise HTTPException(400, f"Could not parse file: {e}")

    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    missing = [c for c in REQUIRED_CANDIDATE_COLUMNS if c not in df.columns]
    if missing:
        raise HTTPException(400, f"Missing required columns: {missing}. Found: {list(df.columns)}")

    db = SessionLocal()
    added = 0
    skipped = 0
    for _, row in df.iterrows():
        s_no = int(row["s_no"])
        existing = db.query(Candidate).filter(Candidate.s_no == s_no).first()
        if existing:
            skipped += 1
            continue
        c = Candidate(
            s_no=s_no,
            name=row.get("name", ""),
            email=row.get("email", ""),
            college=row.get("college", ""),
            branch=row.get("branch", ""),
            cgpa=float(row["cgpa"]) if pd.notna(row.get("cgpa")) else None,
            best_ai_project=row.get("best_ai_project", ""),
            research_work=row.get("research_work") if pd.notna(row.get("research_work")) else None,
            github_profile=row.get("github") if pd.notna(row.get("github")) else None,
            resume_link=row.get("resume", ""),
            status="uploaded",
        )
        db.add(c)
        added += 1
    db.commit()
    total = db.query(Candidate).count()
    db.close()
    return {"status": "ok", "added": added, "skipped_duplicates": skipped, "total_candidates": total}


@app.post("/evaluate")
async def evaluate(job_description: str = Form(...)):
    """Run AI resume evaluation + GitHub analysis for all 'uploaded' candidates."""
    db = SessionLocal()
    candidates = db.query(Candidate).filter(Candidate.status == "uploaded").all()

    if not candidates:
        db.close()
        return {"status": "no_candidates_to_evaluate", "count": 0}

    results = []
    for c in candidates:
        resume_text = download_and_extract(c.resume_link)
        c.resume_text = resume_text[:10000] if resume_text else ""

        ai_result = evaluate_resume(resume_text, job_description, {
            "college": c.college, "branch": c.branch, "cgpa": c.cgpa,
            "best_ai_project": c.best_ai_project, "research_work": c.research_work
        })

        if c.github_profile:
            gh_result = analyze_github(c.github_profile)
        else:
            gh_result = {"github_score": 0, "details": "No GitHub profile provided"}

        c.jd_score = ai_result.get("jd_match_score", 0)
        c.github_score = gh_result.get("github_score", 0)
        c.github_details = str(gh_result)
        c.explanation = ai_result.get("explanation", "")

        # Pre-test combined score: resume/JD relevance weighted higher than GitHub
        c.final_score = round(c.jd_score * 0.6 + c.github_score * 0.4, 2)
        c.status = "evaluated"
        db.commit()
        results.append({"s_no": c.s_no, "name": c.name, "jd_score": c.jd_score,
                         "github_score": c.github_score, "final_score": c.final_score})

    db.close()
    return {"status": "evaluated", "count": len(candidates), "results": results}


@app.get("/candidates")
def get_candidates(status: str = None):
    db = SessionLocal()
    q = db.query(Candidate)
    if status:
        q = q.filter(Candidate.status == status)
    candidates = q.order_by(Candidate.final_score.desc().nullslast()).all()
    db.close()
    return [
        {
            "id": c.id, "s_no": c.s_no, "name": c.name, "email": c.email, "college": c.college,
            "branch": c.branch, "cgpa": c.cgpa, "github_profile": c.github_profile,
            "jd_score": c.jd_score, "github_score": c.github_score,
            "test_la_score": c.test_la_score, "test_code_score": c.test_code_score,
            "final_score": c.final_score, "status": c.status,
            "explanation": c.explanation, "meet_link": c.meet_link,
            "interview_time": c.interview_time,
        }
        for c in candidates
    ]


@app.get("/candidates/{candidate_id}")
def get_candidate_detail(candidate_id: int):
    db = SessionLocal()
    c = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    db.close()
    if not c:
        raise HTTPException(404, "Candidate not found")
    return {
        "id": c.id, "s_no": c.s_no, "name": c.name, "email": c.email, "college": c.college,
        "branch": c.branch, "cgpa": c.cgpa, "best_ai_project": c.best_ai_project,
        "research_work": c.research_work, "github_profile": c.github_profile,
        "resume_link": c.resume_link, "jd_score": c.jd_score,
        "github_score": c.github_score, "github_details": c.github_details,
        "test_la_score": c.test_la_score, "test_code_score": c.test_code_score,
        "final_score": c.final_score, "status": c.status, "explanation": c.explanation,
    }


@app.post("/shortlist")
async def shortlist(threshold: float = Form(60), test_link: str = Form(...)):
    """Send test-link emails to all evaluated candidates scoring above threshold."""
    db = SessionLocal()
    candidates = db.query(Candidate).filter(
        Candidate.status == "evaluated", Candidate.final_score >= threshold
    ).all()

    sent_results = []
    for c in candidates:
        result = send_test_link(c.email, c.name, test_link)
        if result.get("sent"):
            c.status = "shortlisted"
            db.commit()
        sent_results.append({"s_no": c.s_no, "name": c.name, "email": c.email, **result})

    db.close()
    return {"shortlisted": len(candidates), "details": sent_results}


@app.post("/upload-test-results")
async def upload_test_results(file: UploadFile = File(...)):
    """Upload test results (.csv or .xlsx). Matched to candidates by s_no.
    Required columns: s_no, test_la, test_code."""
    try:
        contents = await file.read()
        df = _read_test_results_table(file, contents)
    except Exception as e:
        raise HTTPException(400, f"Could not parse file: {e}")

    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    required = ["s_no", "test_la", "test_code"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(400, f"Missing required columns: {missing}. Found: {list(df.columns)}")

    db = SessionLocal()
    updated = 0
    not_found = []
    for _, row in df.iterrows():
        s_no = int(row["s_no"])
        c = db.query(Candidate).filter(Candidate.s_no == s_no).first()
        if not c:
            not_found.append(s_no)
            continue
        c.test_la_score = float(row["test_la"])
        c.test_code_score = float(row["test_code"])
        test_avg = (c.test_la_score + c.test_code_score) / 2
        pre_test_score = c.final_score or 0
        # Final blended score: 50% pre-test evaluation, 50% test performance
        c.final_score = round(pre_test_score * 0.5 + test_avg * 0.5, 2)
        c.status = "tested"
        db.commit()
        updated += 1

    db.close()
    return {"status": "updated", "updated_count": updated, "not_found_s_no": not_found}


@app.post("/schedule-interviews")
async def schedule_interviews(threshold: float = Form(70), start_in_days: int = Form(1)):
    """Schedule Google Calendar interviews + Meet links for tested candidates above threshold."""
    db = SessionLocal()
    candidates = db.query(Candidate).filter(
        Candidate.status == "tested", Candidate.final_score >= threshold
    ).all()

    base_time = datetime.datetime.now() + datetime.timedelta(days=start_in_days)
    base_time = base_time.replace(hour=10, minute=0, second=0, microsecond=0)

    results = []
    for i, c in enumerate(candidates):
        slot = base_time + datetime.timedelta(minutes=30 * i)
        cal_result = schedule_interview(c.email, c.name, slot)

        if cal_result.get("success"):
            c.status = "interview_scheduled"
            c.meet_link = cal_result.get("meet_link")
            c.interview_time = slot.isoformat()
            db.commit()
            send_interview_invite(c.email, c.name, c.meet_link, slot.strftime("%Y-%m-%d %H:%M IST"))

        results.append({
            "s_no": c.s_no, "name": c.name, "email": c.email,
            "scheduled": cal_result.get("success", False),
            "meet_link": cal_result.get("meet_link"),
            "time": slot.isoformat(),
            "error": cal_result.get("error"),
        })

    db.close()
    return {"scheduled_count": sum(1 for r in results if r["scheduled"]), "details": results}


@app.delete("/reset")
def reset_all_data():
    """Dev utility: wipe all candidate data."""
    db = SessionLocal()
    db.query(Candidate).delete()
    db.commit()
    db.close()
    return {"status": "all candidate data cleared"}
