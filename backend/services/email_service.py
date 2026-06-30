import os
import smtplib
from email.mime.text import MIMEText


def send_test_link(to_email: str, candidate_name: str, test_link: str) -> dict:
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_APP_PASSWORD")

    if not smtp_email or not smtp_password:
        return {"sent": False, "error": "SMTP credentials not configured"}

    body = f"""Hi {candidate_name},

Congratulations! You've been shortlisted for the next round of our hiring process.

Please complete your assessment using the link below:
{test_link}

Best regards,
Recruitment Team"""

    msg = MIMEText(body)
    msg["Subject"] = "You're shortlisted - Complete your assessment"
    msg["From"] = smtp_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
        return {"sent": True}
    except Exception as e:
        return {"sent": False, "error": str(e)}


def send_interview_invite(to_email: str, candidate_name: str, meet_link: str, interview_time: str) -> dict:
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_APP_PASSWORD")

    if not smtp_email or not smtp_password:
        return {"sent": False, "error": "SMTP credentials not configured"}

    body = f"""Hi {candidate_name},

Your interview has been scheduled for {interview_time}.

Join via Google Meet: {meet_link}

Best regards,
Recruitment Team"""

    msg = MIMEText(body)
    msg["Subject"] = "Interview Scheduled"
    msg["From"] = smtp_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
        return {"sent": True}
    except Exception as e:
        return {"sent": False, "error": str(e)}
