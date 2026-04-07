# ShiftSync — Project Structure

```
shift-sync/
├── app.py                  # Flask app factory & entry point
├── config.py               # All configuration (env vars, constants)
├── requirements.txt        # Python dependencies
├── .env.example            # Template for secrets
├── render.yaml             # Render hosting config
│
├── auth/
│   ├── __init__.py
│   └── google_oauth.py     # OAuth2 flow: build flow, get token, refresh
│
├── calendar_sync/
│   ├── __init__.py
│   └── gcal.py             # Google Calendar API: create/check events
│
├── csv_parser/
│   ├── __init__.py
│   └── parser.py           # CSV ingestion, validation, normalization
│
├── routes/
│   ├── __init__.py
│   ├── auth_routes.py      # /login  /oauth2callback  /logout
│   └── upload_routes.py    # /upload  /sync  /status
│
├── static/
│   ├── style.css
│   └── app.js
│
└── templates/
    └── index.html
```
