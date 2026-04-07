"""
routes/upload_routes.py

Routes:
  POST /upload   → accept CSV or XLSX, parse it, return preview JSON
  POST /sync     → take parsed shifts from session, push to Google Calendar
"""

import os
import tempfile
import uuid
from datetime import date, time as dtime
from flask import Blueprint, request, jsonify, session, Response
from auth import is_authenticated, load_credentials_from_session
from csv_parser import parse_csv
from csv_parser.xlsx_parser import parse_xlsx_schedule
from calendar_sync import sync_shifts
from config import Config

upload_bp = Blueprint("upload", __name__)


def _allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS
    )

def _get_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[1].lower() if "." in filename else ""

def _require_auth():
    if not is_authenticated():
        return jsonify({"error": "Not authenticated. Please log in first."}), 401
    return None

def _serialize_shifts(shifts: list[dict]) -> list[dict]:
    out = []
    for s in shifts:
        out.append({
            "employee":   s["employee"],
            "date":       s["date"].isoformat(),
            "start_time": s["start_time"].strftime("%H:%M"),
            "end_time":   s["end_time"].strftime("%H:%M"),
            "notes":      s.get("notes", ""),
            "location":   s.get("location", ""),
            "role":       s.get("role", ""),
        })
    return out


@upload_bp.route("/upload", methods=["POST"])
def upload_csv():
    auth_error = _require_auth()
    if auth_error:
        return auth_error

    if "file" not in request.files:
        return jsonify({"error": "No file part in request."}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not _allowed_file(file.filename):
        return jsonify({"error": "Only .xlsx and .csv files are accepted."}), 400

    ext = _get_extension(file.filename)

    try:
        if ext == "xlsx":
            # openpyxl needs a real path, so save to a temp file first
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name
            try:
                shifts, errors = parse_xlsx_schedule(tmp_path)
            finally:
                os.unlink(tmp_path)
        else:
            shifts, errors = parse_csv(file)

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    if not shifts and errors:
        return jsonify({
            "error": "No valid shifts found. Check the errors list.",
            "errors": errors,
        }), 422

    if not shifts:
        return jsonify({"error": "No shifts found in this file."}), 422

    serialized = _serialize_shifts(shifts)
    return jsonify({
        "shifts":      serialized,
        "errors":      errors,
        "total":       len(serialized),
        "error_count": len(errors),
    })


@upload_bp.route("/sync", methods=["POST"])
def sync_to_calendar():
    auth_error = _require_auth()
    if auth_error:
        return auth_error

    pending = request.get_json(silent=True)
    if not pending:
        return jsonify({"error": "No shifts to sync."}), 400

    credentials = load_credentials_from_session()
    if not credentials:
        return jsonify({"error": "Could not load credentials. Please log in again."}), 401

    from datetime import date, time as dtime
    shifts = []
    for s in pending:
        shifts.append({
            **s,
            "date":       date.fromisoformat(s["date"]),
            "start_time": dtime.fromisoformat(s["start_time"]),
            "end_time":   dtime.fromisoformat(s["end_time"]),
        })

    try:
        result = sync_shifts(credentials, shifts)
    except Exception as exc:
        return jsonify({"error": f"Sync failed: {exc}"}), 500

    return jsonify(result)


@upload_bp.route("/download-ics", methods=["POST"])
def download_ics():
    shifts_raw = request.get_json(silent=True)
    if not shifts_raw:
        return jsonify({"error": "No shifts provided."}), 400

    tz = Config.DEFAULT_TIMEZONE
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ShiftSync//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for s in shifts_raw:
        shift_date = date.fromisoformat(s["date"])
        start = dtime.fromisoformat(s["start_time"])
        end   = dtime.fromisoformat(s["end_time"])

        dtstart = shift_date.strftime("%Y%m%d") + "T" + start.strftime("%H%M%S")
        dtend   = shift_date.strftime("%Y%m%d") + "T" + end.strftime("%H%M%S")
        summary = f"Work Shift — {s['employee']}"
        if s.get("role"):
            summary += f" ({s['role']})"

        lines += [
            "BEGIN:VEVENT",
            f"UID:{uuid.uuid4()}@shiftsync",
            f"DTSTART;TZID={tz}:{dtstart}",
            f"DTEND;TZID={tz}:{dtend}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:Synced by ShiftSync",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    ics_content = "\r\n".join(lines) + "\r\n"

    return Response(
        ics_content,
        mimetype="text/calendar",
        headers={"Content-Disposition": "attachment; filename=shifts.ics"},
    )
