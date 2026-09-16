"""
Google Services Integration (Drive, Gmail, Calendar)
Uses the official Google Python client libraries. Requires OAuth client secrets
(file path stored in `google_client_secrets_path`) and a token file
(`google_token_path`, optional). Scopes cover Drive, Gmail and Calendar read/write.

Capabilities: search_drive, create_calendar_event, today_meetings, search_gmail,
draft_email, send_email.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.integrations.credentials import get_setting, is_configured, missing_for

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]

_cache = {}


def is_available() -> bool:
    return is_configured("google_client_secrets_path")


def _load_services() -> Dict[str, Any]:
    """Authenticates once and returns cached Drive/Gmail/Calendar service objects."""
    if _cache.get("services"):
        return _cache["services"]
    if not is_available():
        _, hint = missing_for("google_client_secrets_path")
        raise RuntimeError(hint)

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError("Google libraries are missing. Run: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2")

    secrets = get_setting("google_client_secrets_path")
    token_path = get_setting("google_token_path") or os.path.join(os.path.dirname(secrets), "token.json")
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(secrets, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    services = {
        "drive": build("drive", "v3", credentials=creds),
        "gmail": build("gmail", "v1", credentials=creds),
        "calendar": build("calendar", "v3", credentials=creds),
    }
    _cache["services"] = services
    return services


def _service(name: str):
    return _load_services()[name]


def _srv_error(e) -> Dict[str, Any]:
    return {"success": False, "error": str(e)}


# ==========================================================
# GOOGLE DRIVE
# ==========================================================
def search_drive(query: str, limit: int = 10) -> Dict[str, Any]:
    """Searches Google Drive for files matching a name/text query."""
    try:
        service = _service("drive")
        q = f"name contains '{query}' and trashed = false"
        results = service.files().list(q=q, pageSize=limit, fields="files(id,name,mimeType,size,modifiedTime)").execute()
        files = [{"id": f.get("id"), "name": f.get("name"), "mime_type": f.get("mimeType"),
                  "size": f.get("size"), "modified": f.get("modifiedTime"),
                  "url": f"https://drive.google.com/file/d/{f.get('id')}/view"} for f in results.get("files", [])]
        return {"success": True, "files": files, "count": len(files), "output": f"Found {len(files)} matching file(s) in Drive."}
    except Exception as e:
        return _srv_error(e)


def find_drive_file(name: str) -> Dict[str, Any]:
    return search_drive(name, limit=5)


# ==========================================================
# GOOGLE CALENDAR
# ==========================================================
def today_meetings() -> Dict[str, Any]:
    """Lists calendar events for today (and upcoming)."""
    try:
        service = _service("calendar")
        now = datetime.now().astimezone()
        start = now.isoformat()
        end = (now + timedelta(hours=24)).isoformat()
        events = service.events().list(calendarId="primary", timeMin=start, timeMax=end,
                                       singleEvents=True, orderBy="startTime").execute()
        items = []
        for ev in events.get("items", []):
            start_dt = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
            items.append({"summary": ev.get("summary"), "start": start_dt, "end": ev.get("end", {}).get("dateTime"),
                          "location": ev.get("location"), "html_link": ev.get("htmlLink"),
                          "status": ev.get("status")})
        return {"success": True, "count": len(items), "meetings": items,
                "output": f"You have {len(items)} upcoming event(s) today."}
    except Exception as e:
        return _srv_error(e)


def create_calendar_event(summary: str, start_time: str = None, end_time: str = None,
                          duration_minutes: int = 60, description: str = "", location: str = "") -> Dict[str, Any]:
    """
    Creates a calendar event.
    start_time/end_time: ISO strings (e.g. "2026-09-16T14:00:00"). If missing,
    starts one hour from now.
    """
    try:
        service = _service("calendar")
        if not start_time:
            start_dt = datetime.now().astimezone() + timedelta(hours=1)
            end_dt = start_dt + timedelta(minutes=int(duration_minutes))
        else:
            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.fromisoformat(end_time) if end_time else start_dt + timedelta(minutes=int(duration_minutes))
        event = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {"dateTime": start_dt.isoformat()},
            "end": {"dateTime": end_dt.isoformat()},
        }
        created = service.events().insert(calendarId="primary", body=event).execute()
        return {"success": True, "id": created.get("id"), "link": created.get("htmlLink"),
                "start": created.get("start", {}).get("dateTime"),
                "output": f"Created calendar event '{summary}' at {created.get('start', {}).get('dateTime')}."}
    except Exception as e:
        return _srv_error(e)


# ==========================================================
# GMAIL
# ==========================================================
def search_gmail(query: str, limit: int = 10) -> Dict[str, Any]:
    """Searches Gmail messages (e.g. 'from:me has:attachment resume')."""
    try:
        service = _service("gmail")
        resp = service.users().messages().list(userId="me", q=query, maxResults=limit).execute()
        ids = [m["id"] for m in resp.get("messages", [])]
        messages = []
        for mid in ids:
            msg = service.users().messages().get(userId="me", id=mid, format="metadata",
                                                 metadataHeaders=["Subject", "From", "Date"]).execute()
            payload = msg.get("payload", {})
            headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
            messages.append({"id": mid, "subject": headers.get("subject"), "from": headers.get("from"),
                             "date": headers.get("date"), "snippet": msg.get("snippet")})
        return {"success": True, "count": len(messages), "messages": messages,
                "output": f"Found {len(messages)} message(s) matching '{query}'."}
    except Exception as e:
        return _srv_error(e)


def draft_email(to: str, subject: str, body: str) -> Dict[str, Any]:
    """Saves a draft Gmail message (no sending)."""
    try:
        service = _service("gmail")
        message = _mime_message(to, subject, body)
        draft = service.users().drafts().create(userId="me", body={"message": {"raw": message}}).execute()
        return {"success": True, "draft_id": draft.get("id"), "to": to, "subject": subject,
                "output": f"Draft created for {to} with subject '{subject}' (not sent)."}
    except Exception as e:
        return _srv_error(e)


def send_email(to: str, subject: str, body: str, confirm: bool = False) -> Dict[str, Any]:
    """Sends an email. Requires confirm=True (sending is treated as sensitive)."""
    if not confirm:
        return {"success": False, "error": "Refusing to send email without confirmation. Retry with confirm=True."}
    try:
        service = _service("gmail")
        message = _mime_message(to, subject, body)
        sent = service.users().messages().send(userId="me", body={"raw": message}).execute()
        return {"success": True, "id": sent.get("id"), "to": to, "subject": subject,
                "output": f"Email sent to {to} with subject '{subject}'."}
    except Exception as e:
        return _srv_error(e)


def _mime_message(to: str, subject: str, body: str) -> str:
    from email.mime.text import MIMEText
    import base64
    msg = MIMEText(body, "html")
    msg["To"] = to
    msg["Subject"] = subject
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()