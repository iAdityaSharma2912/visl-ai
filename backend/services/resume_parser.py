import io
import re
import requests
from pypdf import PdfReader
from docx import Document


def _to_direct_download(url: str) -> str:
    """Convert common share links (e.g. Google Drive) into direct-download links."""
    if "drive.google.com" in url:
        if "/file/d/" in url:
            file_id = url.split("/file/d/")[1].split("/")[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        if "id=" in url:
            file_id = url.split("id=")[1].split("&")[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url


def _drive_file_id(url: str) -> str | None:
    if "drive.google.com" not in url:
        return None
    if "/file/d/" in url:
        return url.split("/file/d/")[1].split("/")[0]
    if "id=" in url:
        return url.split("id=")[1].split("&")[0]
    return None


def _fetch_with_drive_confirm(session: requests.Session, url: str, timeout: int) -> requests.Response:
    """Google Drive shows an HTML 'can't scan for viruses' interstitial for large/flagged
    files instead of the actual content. Detect it and retry with the confirm token."""
    r = session.get(url, timeout=timeout, allow_redirects=True)
    content_type = r.headers.get("content-type", "").lower()

    if "text/html" in content_type and "drive.google.com" in url:
        # Look for a confirm token in the interstitial page (older pattern)
        match = re.search(r'confirm=([0-9A-Za-z_-]+)', r.text)
        file_id = _drive_file_id(url)
        if match and file_id:
            confirm_url = f"https://drive.google.com/uc?export=download&confirm={match.group(1)}&id={file_id}"
            r = session.get(confirm_url, timeout=timeout, allow_redirects=True)
        elif file_id:
            # Newer Drive interstitial requires the uuid cookie param; try the alternate endpoint
            alt_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
            r = session.get(alt_url, timeout=timeout, allow_redirects=True)

    return r


def download_and_extract(resume_url: str) -> str:
    """Download a resume from a URL and extract plain text from PDF/DOCX/text."""
    if not resume_url or not isinstance(resume_url, str):
        return ""

    url = _to_direct_download(resume_url.strip())

    try:
        session = requests.Session()
        r = _fetch_with_drive_confirm(session, url, timeout=20)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "").lower()

        if content_type.startswith("application/pdf") or r.content[:4] == b"%PDF":
            reader = PdfReader(io.BytesIO(r.content))
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
            if not text.strip():
                return "ERROR_FETCHING_RESUME: PDF downloaded but contained no extractable text (possibly scanned/image-only)"
            return text.strip()

        if "wordprocessingml" in content_type or r.content[:2] == b"PK":
            try:
                doc = Document(io.BytesIO(r.content))
                return "\n".join(p.text for p in doc.paragraphs).strip()
            except Exception:
                pass

        if "text/html" in content_type:
            return "ERROR_FETCHING_RESUME: Received an HTML page instead of the resume file (link may require sign-in, be too large for Drive's direct-download, or be private)"

        # Fallback: treat as plain text
        return r.text[:20000]

    except Exception as e:
        return f"ERROR_FETCHING_RESUME: {e}"
