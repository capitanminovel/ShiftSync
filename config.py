import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.environ.get(
        "GOOGLE_REDIRECT_URI", "http://localhost:5000/oauth2callback"
    )

    # OAuth scopes needed
    GOOGLE_SCOPES = [
        "https://www.googleapis.com/auth/calendar.events",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
    ]

    # CSV upload
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB limit
    ALLOWED_EXTENSIONS = {"csv", "xlsx"}

    # Calendar defaults
    DEFAULT_TIMEZONE = os.environ.get("DEFAULT_TIMEZONE", "America/Chicago")
    CALENDAR_ID = os.environ.get("CALENDAR_ID", "primary")
