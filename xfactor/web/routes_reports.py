"""Home page, views, stored procedures and the multi-join report."""
from __future__ import annotations

from flask import Blueprint, flash, render_template, request
from sqlalchemy import func, select

from xfactor.db import session_scope
from xfactor.repository import reports
from xfactor.repository.crud import MODELS
from xfactor.web import can_edit

bp = Blueprint("reports", __name__)


@bp.route("/")
def home():
    with session_scope() as db:
        counts = {name: db.scalar(select(func.count()).select_from(model)) for name, model in MODELS.items()}
        summary = reports.read_view(db, "v_series_summary")
    return render_template("home.html", counts=counts, total=sum(counts.values()), summary=summary)


@bp.route("/views/<name>")
def view(name: str):
    if name not in reports.VIEW_NAMES:
        return render_template("message.html", message="Unknown view"), 404
    series = request.args.get("series", type=int)
    filters = {"series_number": series} if series and name != "v_mentor_stats" else {}
    with session_scope() as db:
        table = reports.read_view(db, name, limit=500, **filters)
    return render_template("report.html", title=f"VIEW {name}", table=table, view_name=name, series=series)


@bp.route("/procedures", methods=["GET", "POST"])
def procedures():
    table, title = None, None
    form = request.form if request.method == "POST" else request.args
    proc = form.get("proc")
    try:
        with session_scope() as db:
            if proc == "leaderboard":
                number = int(form.get("series", "7"))
                table, title = reports.series_leaderboard(db, number), f"CALL sp_series_leaderboard({number})"
            elif proc == "journey":
                act = form.get("act", "").strip() or "One Direction"
                table, title = reports.act_journey(db, act), f"CALL sp_act_journey('{act}')"
            elif proc == "showdown" and request.method == "POST":
                if not can_edit():
                    flash("Log in as editor to run a write procedure.", "error")
                else:
                    rows = reports.record_showdown_result(
                        db, int(form["series"]), int(form["week"]), form["act"], form["result"])
                    flash(f"sp_record_showdown_result updated {rows} row(s) (OUT p_rows_updated).", "ok")
    except (KeyError, ValueError) as exc:
        flash(f"Invalid input: {exc}", "error")
    return render_template("procedures.html", table=table, title=title, form=form)


@bp.route("/reports/mentor-songs")
def mentor_songs():
    mentor = request.args.get("mentor", "Cowell")
    with session_scope() as db:
        table = reports.songs_by_mentor(db, mentor, limit=500)
        top = reports.most_performed_songs(db)
    return render_template("join.html", table=table, top=top, mentor=mentor)
