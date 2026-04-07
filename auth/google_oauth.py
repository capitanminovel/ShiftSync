"""
auth/google_oauth.py

Responsibilities:
- Build the OAuth2 authorization URL
- Exchange an authorization code for credentials
- Serialize / deserialize credentials to/from the session
- Check if the current session has valid (non-expired) credentials
"""

import base64
import hashlib
import os

from flask import session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from config import Config


# ---------------------------------------------------------------------------
# Flow helpers
# ---------------------------------------------------------------------------

def build_flow() -> Flow:
    """Create a new OAuth2 Flow from client secrets config."""
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": Config.GOOGLE_CLIENT_ID,
                "client_secret": Config.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [Config.GOOGLE_REDIRECT_URI],
            }
        },
        scopes=Config.GOOGLE_SCOPES,
        redirect_uri=Config.GOOGLE_REDIRECT_URI,
    )


def _generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge (S256)."""
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def get_authorization_url() -> tuple[str, str]:
    """
    Generate the Google OAuth consent-screen URL.

    Returns:
        (authorization_url, state)
    """
    flow = build_flow()
    code_verifier, code_challenge = _generate_pkce_pair()
    session["pkce_code_verifier"] = code_verifier
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    return authorization_url, state


def exchange_code_for_credentials(code: str) -> Credentials:
    """
    Exchange an authorization code for Google credentials.

    Args:
        code: The `code` query parameter from the OAuth callback.

    Returns:
        A google.oauth2.credentials.Credentials object.
    """
    flow = build_flow()
    code_verifier = session.pop("pkce_code_verifier", None)
    flow.fetch_token(code=code, code_verifier=code_verifier)
    return flow.credentials


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def save_credentials_to_session(credentials: Credentials) -> None:
    """Serialize credentials into the Flask session."""
    session["google_credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or []),
    }


def load_credentials_from_session() -> Credentials | None:
    """
    Deserialize credentials from the Flask session.

    Returns:
        Credentials object, or None if the session has no credentials.
    """
    creds_data = session.get("google_credentials")
    if not creds_data:
        return None

    return Credentials(
        token=creds_data["token"],
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data["token_uri"],
        client_id=creds_data["client_id"],
        client_secret=creds_data["client_secret"],
        scopes=creds_data["scopes"],
    )


def is_authenticated() -> bool:
    """Return True if the session contains Google credentials."""
    return "google_credentials" in session


def clear_credentials() -> None:
    """Remove Google credentials from the session (logout)."""
    session.pop("google_credentials", None)
