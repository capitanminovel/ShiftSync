"""
routes/auth_routes.py

Routes:
  GET /login           → redirect to Google OAuth consent screen
  GET /oauth2callback  → handle OAuth callback, save credentials
  GET /logout          → clear session
  GET /auth/status     → JSON: is the user authenticated?
"""

from flask import Blueprint, redirect, request, session, jsonify, url_for
from auth import (
    get_authorization_url,
    exchange_code_for_credentials,
    save_credentials_to_session,
    is_authenticated,
    clear_credentials,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login")
def login():
    """Kick off the Google OAuth flow."""
    authorization_url, state = get_authorization_url()
    session["oauth_state"] = state
    return redirect(authorization_url)


@auth_bp.route("/oauth2callback")
def oauth2callback():
    """Handle the redirect back from Google."""
    # Basic CSRF check
    returned_state = request.args.get("state")
    if returned_state != session.get("oauth_state"):
        return jsonify({"error": "State mismatch — possible CSRF attack."}), 400

    error = request.args.get("error")
    if error:
        return jsonify({"error": f"OAuth error: {error}"}), 400

    code = request.args.get("code")
    if not code:
        return jsonify({"error": "No authorization code received."}), 400

    credentials = exchange_code_for_credentials(code)
    save_credentials_to_session(credentials)

    return redirect(url_for("index"))


@auth_bp.route("/logout")
def logout():
    """Clear the session and send back to home."""
    clear_credentials()
    session.clear()
    return redirect(url_for("index"))


@auth_bp.route("/auth/status")
def auth_status():
    """JSON endpoint polled by the frontend to check login state."""
    return jsonify({"authenticated": is_authenticated()})
