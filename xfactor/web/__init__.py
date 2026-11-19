"""Flask GUI. Run locally with:  python -m xfactor.web"""
from __future__ import annotations

import os
import secrets

from flask import Flask, abort, request, session


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(16)
    app.config["EDIT_PASSWORD"] = os.getenv("EDIT_PASSWORD")  # set when deployed publicly

    from xfactor.web.routes_ask import bp as ask_bp
    from xfactor.web.routes_reports import bp as reports_bp
    from xfactor.web.routes_tables import bp as tables_bp

    app.register_blueprint(reports_bp)
    app.register_blueprint(tables_bp)
    app.register_blueprint(ask_bp)
    app.jinja_env.globals["zip"] = zip

    @app.before_request
    def csrf_protect() -> None:
        if request.method == "POST":
            token = session.get("csrf_token")
            if not token or token != request.form.get("csrf_token"):
                abort(400, "Invalid or missing CSRF token. Reload the page and try again.")

    @app.context_processor
    def inject_globals() -> dict:
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        from xfactor.repository.crud import MODELS
        return {
            "csrf_token": session["csrf_token"],
            "table_names": sorted(MODELS),
            "can_edit": can_edit(),
        }

    return app


def can_edit() -> bool:
    """Writes are open locally; when EDIT_PASSWORD is set (public deploy) a login is needed."""
    from flask import current_app
    return not current_app.config.get("EDIT_PASSWORD") or session.get("editor") is True
