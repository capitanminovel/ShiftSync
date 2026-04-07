"""
app.py — Flask application factory and entry point
"""

import os
from flask import Flask, render_template
from config import Config
from routes import auth_bp, upload_bp

# Allow HTTP for local OAuth testing (remove in production)
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(upload_bp)

    # Main page route lives here (not in a blueprint) to keep it simple
    @app.route("/")
    def index():
        return render_template("index.html")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=Config.DEBUG, port=5000)
