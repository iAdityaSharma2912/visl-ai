import json
import os
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Any OpenRouter-supported model works here. Pick one based on cost/quality tradeoff.
# Examples: "anthropic/claude-sonnet-4-6", "openai/gpt-4o-mini", "google/gemini-2.0-flash-001"
MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-6")


def _safe_json_parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass
        return {
            "jd_match_score": 0,
            "strengths": [],
            "gaps": ["AI evaluation failed to parse"],
            "explanation": "Could not parse AI response."
        }


def evaluate_resume(resume_text: str, jd_text: str, candidate_meta: dict) -> dict:
    if resume_text.startswith("ERROR_FETCHING_RESUME"):
        return {
            "jd_match_score": 0,
            "strengths": [],
            "gaps": ["Resume could not be downloaded/parsed"],
            "explanation": resume_text
        }

    if not OPENROUTER_API_KEY:
        return {
            "jd_match_score": 0,
            "strengths": [],
            "gaps": [],
            "explanation": "OPENROUTER_API_KEY not set in environment."
        }

    prompt = f"""You are an expert technical recruiter evaluating a candidate against a job description.

JOB DESCRIPTION:
{jd_text}

CANDIDATE PROFILE:
College: {candidate_meta.get('college')}
Branch: {candidate_meta.get('branch')}
CGPA: {candidate_meta.get('cgpa')}
Best AI Project: {candidate_meta.get('best_ai_project')}
Research Work: {candidate_meta.get('research_work')}

RESUME TEXT (extracted):
{resume_text[:6000] if resume_text else "Not available"}

Evaluate how well this candidate matches the job description. Consider skills overlap,
project relevance, academic background, and research experience.

Return ONLY valid JSON with this exact schema, no markdown fences, no preamble:
{{
  "jd_match_score": <integer 0-100>,
  "strengths": ["short point", "short point"],
  "gaps": ["short point", "short point"],
  "explanation": "2-3 sentence reasoning explaining the score"
}}"""

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "https://visl-screening.local"),
                "X-Title": "Visl AI Candidate Screening",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.2,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        raw_text = data["choices"][0]["message"]["content"]
        result = _safe_json_parse(raw_text)
        result["jd_match_score"] = float(result.get("jd_match_score", 0) or 0)
        return result
    except requests.exceptions.HTTPError as e:
        error_body = ""
        try:
            error_body = e.response.json()
        except Exception:
            error_body = e.response.text if e.response is not None else str(e)
        return {
            "jd_match_score": 0,
            "strengths": [],
            "gaps": [],
            "explanation": f"OpenRouter API error: {error_body}"
        }
    except Exception as e:
        return {
            "jd_match_score": 0,
            "strengths": [],
            "gaps": [],
            "explanation": f"AI evaluation error: {e}"
        }
