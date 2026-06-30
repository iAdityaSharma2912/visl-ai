import os
import pickle
import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_PATH = "token.pickle"
CREDS_PATH = "credentials.json"


def get_calendar_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_PATH):
                raise FileNotFoundError(
                    "credentials.json not found. Download OAuth client credentials "
                    "from Google Cloud Console and place in backend/."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    return build("calendar", "v3", credentials=creds)


def schedule_interview(candidate_email: str, candidate_name: str, start_time: datetime.datetime) -> dict:
    try:
        service = get_calendar_service()
        end_time = start_time + datetime.timedelta(minutes=30)

        event = {
            "summary": f"Interview: {candidate_name}",
            "description": f"Automated interview scheduling for candidate {candidate_name}",
            "start": {"dateTime": start_time.isoformat(), "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": end_time.isoformat(), "timeZone": "Asia/Kolkata"},
            "attendees": [{"email": candidate_email}],
            "conferenceData": {
                "createRequest": {
                    "requestId": f"meet-{candidate_email}-{int(start_time.timestamp())}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"}
                }
            },
        }

        created = service.events().insert(
            calendarId="primary",
            body=event,
            conferenceDataVersion=1,
            sendUpdates="all"
        ).execute()

        return {
            "success": True,
            "meet_link": created.get("hangoutLink"),
            "event_link": created.get("htmlLink"),
            "start_time": start_time.isoformat(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
