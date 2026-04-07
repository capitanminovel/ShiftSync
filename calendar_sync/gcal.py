"""
calendar_sync/gcal.py

Responsibilities:
- Build an authenticated Google Calendar API service
- Convert a parsed shift dict into a Calendar event body
- Check whether an identical event already exists (deduplication)
- Create a single event
- Sync a list of shifts, returning a results summary
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import Config


# ---------------------------------------------------------------------------
# Service factory
# ---------------------------------------------------------------------------

def build_calendar_service(credentials: Credentials):
    """Return an authenticated Google Calendar API service object."""
    return build("calendar", "v3", credentials=credentials)


# ---------------------------------------------------------------------------
# Event construction
# ---------------------------------------------------------------------------

def shift_to_event(shift: dict) -> dict:
    """
    Convert a parsed shift dict into a Google Calendar event body.

    The description embeds a deduplication fingerprint so we can
    detect re-uploads of the same shift.
    """
    tz = Config.DEFAULT_TIMEZONE
    shift_date = shift["date"].isoformat()  # "2024-05-20"

    start_dt = f"{shift_date}T{shift['start_time'].strftime('%H:%M:%S')}"
    end_dt   = f"{shift_date}T{shift['end_time'].strftime('%H:%M:%S')}"

    description_parts = [
        f"Employee: {shift['employee']}",
        f"Synced by ShiftSync",
        f"[fingerprint:{_make_fingerprint(shift)}]",
    ]
    if shift.get("role"):
        description_parts.insert(1, f"Role: {shift['role']}")
    if shift.get("notes"):
        description_parts.insert(1, f"Notes: {shift['notes']}")

    event = {
        "summary": _build_summary(shift),
        "description": "\n".join(description_parts),
        "start": {"dateTime": start_dt, "timeZone": tz},
        "end":   {"dateTime": end_dt,   "timeZone": tz},
    }

    if shift.get("location"):
        event["location"] = shift["location"]

    return event


def _build_summary(shift: dict) -> str:
    """Format a human-readable event title."""
    role = f" ({shift['role']})" if shift.get("role") else ""
    return f"Work Shift — {shift['employee']}{role}"


def _make_fingerprint(shift: dict) -> str:
    """
    A deterministic string that uniquely identifies this shift.
    Used to skip duplicate events on re-upload.
    """
    return (
        f"{shift['employee']}|"
        f"{shift['date'].isoformat()}|"
        f"{shift['start_time'].strftime('%H:%M')}|"
        f"{shift['end_time'].strftime('%H:%M')}"
    )


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def event_already_exists(service, calendar_id: str, shift: dict) -> bool:
    """
    Check if a calendar event with a matching fingerprint already exists
    on the same date as the shift.
    """
    fingerprint = _make_fingerprint(shift)
    tz = ZoneInfo(Config.DEFAULT_TIMEZONE)

    # Search within the shift's day
    time_min = datetime(
        shift["date"].year, shift["date"].month, shift["date"].day,
        0, 0, 0, tzinfo=tz
    ).isoformat()
    time_max = datetime(
        shift["date"].year, shift["date"].month, shift["date"].day,
        23, 59, 59, tzinfo=tz
    ).isoformat()

    try:
        result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
        ).execute()
    except HttpError:
        return False  # on error, attempt creation anyway

    for event in result.get("items", []):
        desc = event.get("description", "")
        if f"[fingerprint:{fingerprint}]" in desc:
            return True

    return False


# ---------------------------------------------------------------------------
# Event creation
# ---------------------------------------------------------------------------

def create_event(service, calendar_id: str, event_body: dict) -> dict:
    """
    Insert a single event into Google Calendar.

    Returns:
        The created event resource dict (includes 'id', 'htmlLink', etc.)
    """
    return service.events().insert(
        calendarId=calendar_id,
        body=event_body,
    ).execute()


# ---------------------------------------------------------------------------
# Bulk sync
# ---------------------------------------------------------------------------

def sync_shifts(credentials: Credentials, shifts: list[dict]) -> dict:
    """
    Sync a list of parsed shifts to Google Calendar.

    Skips duplicates. Collects per-shift results.

    Returns:
        {
            "created": int,
            "skipped": int,
            "failed": int,
            "results": [{"shift": ..., "status": "created"|"skipped"|"failed", "detail": ...}]
        }
    """
    service = build_calendar_service(credentials)
    calendar_id = Config.CALENDAR_ID

    summary = {"created": 0, "skipped": 0, "failed": 0, "results": []}

    for shift in shifts:
        result_entry = {"shift": _shift_label(shift)}

        try:
            if event_already_exists(service, calendar_id, shift):
                result_entry["status"] = "skipped"
                result_entry["detail"] = "Duplicate event already on calendar"
                summary["skipped"] += 1
            else:
                event_body = shift_to_event(shift)
                created = create_event(service, calendar_id, event_body)
                result_entry["status"] = "created"
                result_entry["detail"] = created.get("htmlLink", "")
                summary["created"] += 1

        except HttpError as exc:
            result_entry["status"] = "failed"
            result_entry["detail"] = str(exc)
            summary["failed"] += 1

        summary["results"].append(result_entry)

    return summary


def _shift_label(shift: dict) -> str:
    return (
        f"{shift['employee']} on {shift['date'].isoformat()} "
        f"{shift['start_time'].strftime('%H:%M')}–{shift['end_time'].strftime('%H:%M')}"
    )
