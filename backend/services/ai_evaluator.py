import json
import os
import requests

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


def _safe_json_parse(text: str) -> dict:
    original_text = text
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
            "explanation": f"Could not parse AI response. Raw output: {original_text[:300]!r}"
        }


def evaluate_resume(resume_text: str, jd_text: str, candidate_meta: dict) -> dict:
    if resume_text.startswith("ERROR_FETCHING_RESUME"):
        return {
            "jd_match_score": 0,
            "strengths": [],
            "gaps": ["Resume could not be downloaded/parsed"],
            "explanation": resume_text
        }

    if not GEMINI_API_KEY:
        return {
            "jd_match_score": 0,
            "strengths": [],
            "gaps": [],
            "explanation": "GEMINI_API_KEY not set in environment."
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
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 2048,
                    "responseMimeType": "application/json",
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
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
            "explanation": f"Gemini API error: {error_body}"
        }
    except (KeyError, IndexError) as e:
        return {
            "jd_match_score": 0,
            "strengths": [],
            "gaps": [],
            "explanation": f"Gemini API returned an unexpected response shape: {e}. Raw: {str(data)[:500] if 'data' in dir() else 'no response'}"
        }
    except Exception as e:
        return {
            "jd_match_score": 0,
            "strengths": [],
            "gaps": [],
            "explanation": f"AI evaluation error: {e}"
        }